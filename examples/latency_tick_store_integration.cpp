/*
 * Latency Tick Store Integration with Enhanced Schema Registry
 * 
 * This demonstrates how the C++ Latency Tick Store would integrate with
 * the enhanced Schema Registry features including caching, real-time updates,
 * and Arrow schema mapping.
 */

#include <iostream>
#include <string>
#include <memory>
#include <unordered_map>
#include <chrono>
#include <thread>
#include <atomic>
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <arrow/api.h>
#include <arrow/csv/api.h>
#include <arrow/io/api.h>
#include <arrow/result.h>

using json = nlohmann::json;

// Schema Registry Client for C++
class SchemaRegistryClient {
private:
    std::string base_url_;
    std::string auth_token_;
    std::unordered_map<std::string, json> schema_cache_;
    std::unordered_map<std::string, std::chrono::steady_clock::time_point> cache_timestamps_;
    std::chrono::seconds cache_ttl_{600}; // 10 minutes
    std::atomic<bool> running_{false};
    std::thread update_thread_;
    
    // Statistics
    std::atomic<int> cache_hits_{0};
    std::atomic<int> cache_misses_{0};
    std::atomic<int> schema_fetches_{0};

public:
    SchemaRegistryClient(const std::string& base_url, const std::string& auth_token = "")
        : base_url_(base_url), auth_token_(auth_token) {
        curl_global_init(CURL_GLOBAL_DEFAULT);
    }
    
    ~SchemaRegistryClient() {
        stop_monitoring();
        curl_global_cleanup();
    }
    
    // HTTP request helper
    static size_t WriteCallback(void* contents, size_t size, size_t nmemb, std::string* userp) {
        userp->append((char*)contents, size * nmemb);
        return size * nmemb;
    }
    
    json fetch_schema(const std::string& schema_id, const std::string& version = "") {
        // Check cache first
        auto cache_key = schema_id + (version.empty() ? "" : ":" + version);
        auto now = std::chrono::steady_clock::now();
        
        auto cache_it = schema_cache_.find(cache_key);
        if (cache_it != schema_cache_.end()) {
            auto cache_time = cache_timestamps_[cache_key];
            if (now - cache_time < cache_ttl_) {
                cache_hits_++;
                return cache_it->second;
            }
        }
        
        // Fetch from registry
        cache_misses_++;
        schema_fetches_++;
        
        CURL* curl = curl_easy_init();
        if (!curl) {
            throw std::runtime_error("Failed to initialize CURL");
        }
        
        std::string url = base_url_ + "/schema/" + schema_id;
        if (!version.empty()) {
            url += "?version=" + version;
        }
        
        std::string response;
        
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);
        
        if (!auth_token_.empty()) {
            std::string auth_header = "Authorization: Bearer " + auth_token_;
            struct curl_slist* headers = nullptr;
            headers = curl_slist_append(headers, auth_header.c_str());
            curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
        }
        
        CURLcode res = curl_easy_perform(curl);
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        
        curl_easy_cleanup(curl);
        
        if (res != CURLE_OK) {
            throw std::runtime_error("CURL request failed: " + std::string(curl_easy_strerror(res)));
        }
        
        if (http_code != 200) {
            throw std::runtime_error("HTTP request failed with code: " + std::to_string(http_code));
        }
        
        // Parse response
        json response_json = json::parse(response);
        json schema_data = response_json["schema"];
        
        // Cache the result
        schema_cache_[cache_key] = schema_data;
        cache_timestamps_[cache_key] = now;
        
        return schema_data;
    }
    
    // Convert JSON schema to Arrow schema
    std::shared_ptr<arrow::Schema> create_arrow_schema(const json& schema_json) {
        std::vector<std::shared_ptr<arrow::Field>> fields;
        
        // Check if Arrow schema is provided
        if (schema_json.contains("arrow") && schema_json["arrow"].contains("fields")) {
            auto arrow_fields = schema_json["arrow"]["fields"];
            for (const auto& field : arrow_fields) {
                std::string field_name = field["name"];
                auto field_type = field["type"];
                std::string type_name = field_type["name"];
                
                std::shared_ptr<arrow::DataType> arrow_type;
                
                if (type_name == "int32") {
                    arrow_type = arrow::int32();
                } else if (type_name == "int64") {
                    arrow_type = arrow::int64();
                } else if (type_name == "float32") {
                    arrow_type = arrow::float32();
                } else if (type_name == "float64") {
                    arrow_type = arrow::float64();
                } else if (type_name == "utf8") {
                    arrow_type = arrow::utf8();
                } else if (type_name == "timestamp") {
                    std::string unit = field_type.value("unit", "us");
                    if (unit == "us") {
                        arrow_type = arrow::timestamp(arrow::TimeUnit::MICRO);
                    } else if (unit == "ns") {
                        arrow_type = arrow::timestamp(arrow::TimeUnit::NANO);
                    } else {
                        arrow_type = arrow::timestamp(arrow::TimeUnit::SECOND);
                    }
                } else {
                    // Default to string for unknown types
                    arrow_type = arrow::utf8();
                }
                
                fields.push_back(arrow::field(field_name, arrow_type));
            }
        } else {
            // Fallback: create Arrow schema from JSON schema properties
            auto properties = schema_json["properties"];
            for (auto it = properties.begin(); it != properties.end(); ++it) {
                std::string field_name = it.key();
                auto field_schema = it.value();
                std::string json_type = field_schema["type"];
                
                std::shared_ptr<arrow::DataType> arrow_type;
                
                if (json_type == "integer") {
                    arrow_type = arrow::int64();
                } else if (json_type == "number") {
                    arrow_type = arrow::float64();
                } else if (json_type == "string") {
                    arrow_type = arrow::utf8();
                } else {
                    arrow_type = arrow::utf8();
                }
                
                fields.push_back(arrow::field(field_name, arrow_type));
            }
        }
        
        return std::make_shared<arrow::Schema>(fields);
    }
    
    // Start monitoring for schema updates
    void start_monitoring() {
        if (running_.load()) return;
        
        running_.store(true);
        update_thread_ = std::thread([this]() {
            this->monitor_schema_updates();
        });
    }
    
    void stop_monitoring() {
        running_.store(false);
        if (update_thread_.joinable()) {
            update_thread_.join();
        }
    }
    
private:
    void monitor_schema_updates() {
        while (running_.load()) {
            try {
                // Poll for schema updates every 30 seconds
                std::this_thread::sleep_for(std::chrono::seconds(30));
                
                // Clear expired cache entries
                auto now = std::chrono::steady_clock::now();
                std::vector<std::string> expired_keys;
                
                for (const auto& pair : cache_timestamps_) {
                    if (now - pair.second > cache_ttl_) {
                        expired_keys.push_back(pair.first);
                    }
                }
                
                for (const auto& key : expired_keys) {
                    schema_cache_.erase(key);
                    cache_timestamps_.erase(key);
                }
                
            } catch (const std::exception& e) {
                std::cerr << "Error in schema monitoring: " << e.what() << std::endl;
            }
        }
    }
    
public:
    // Get statistics
    json get_stats() {
        return {
            {"cache_hits", cache_hits_.load()},
            {"cache_misses", cache_misses_.load()},
            {"schema_fetches", schema_fetches_.load()},
            {"cache_size", schema_cache_.size()},
            {"cache_hit_ratio", cache_hits_.load() / (double)(cache_hits_.load() + cache_misses_.load())}
        };
    }
};

// Enhanced Latency Tick Store
class LatencyTickStore {
private:
    std::unique_ptr<SchemaRegistryClient> schema_client_;
    std::unordered_map<std::string, std::shared_ptr<arrow::Schema>> arrow_schemas_;
    std::string data_directory_;
    
    // Performance metrics
    std::atomic<int64_t> processed_ticks_{0};
    std::atomic<int64_t> validation_errors_{0};
    std::chrono::steady_clock::time_point start_time_;
    
public:
    LatencyTickStore(const std::string& registry_url, const std::string& data_dir)
        : data_directory_(data_dir) {
        schema_client_ = std::make_unique<SchemaRegistryClient>(registry_url);
        start_time_ = std::chrono::steady_clock::now();
    }
    
    ~LatencyTickStore() {
        if (schema_client_) {
            schema_client_->stop_monitoring();
        }
    }
    
    void initialize() {
        std::cout << "Initializing Latency Tick Store..." << std::endl;
        
        // Start schema monitoring
        schema_client_->start_monitoring();
        
        std::cout << "Latency Tick Store initialized successfully" << std::endl;
    }
    
    bool load_tick_data(const std::string& file_path, const std::string& schema_id, 
                       const std::string& version = "") {
        try {
            std::cout << "Loading tick data from: " << file_path << std::endl;
            std::cout << "Using schema: " << schema_id << (version.empty() ? "" : " v" + version) << std::endl;
            
            // Fetch schema from registry
            json schema_json = schema_client_->fetch_schema(schema_id, version);
            std::cout << "Schema fetched: " << schema_json["title"] << std::endl;
            
            // Create Arrow schema
            auto arrow_schema = schema_client_->create_arrow_schema(schema_json);
            arrow_schemas_[schema_id] = arrow_schema;
            
            std::cout << "Arrow schema created with " << arrow_schema->num_fields() << " fields" << std::endl;
            
            // Load CSV data with Arrow
            auto result = load_csv_with_arrow(file_path, arrow_schema);
            if (!result.ok()) {
                std::cerr << "Failed to load CSV: " << result.status().ToString() << std::endl;
                return false;
            }
            
            auto table = result.ValueOrDie();
            std::cout << "Loaded " << table->num_rows() << " rows, " << table->num_columns() << " columns" << std::endl;
            
            // Process the data
            process_tick_data(table, schema_id);
            
            return true;
            
        } catch (const std::exception& e) {
            std::cerr << "Error loading tick data: " << e.what() << std::endl;
            return false;
        }
    }
    
private:
    arrow::Result<std::shared_ptr<arrow::Table>> load_csv_with_arrow(
        const std::string& file_path, std::shared_ptr<arrow::Schema> schema) {
        
        // Open file
        ARROW_ASSIGN_OR_RAISE(auto input_file, arrow::io::ReadableFile::Open(file_path));
        
        // Create CSV reader
        auto read_options = arrow::csv::ReadOptions::Defaults();
        auto parse_options = arrow::csv::ParseOptions::Defaults();
        auto convert_options = arrow::csv::ConvertOptions::Defaults();
        
        // Set schema
        convert_options.column_types = schema->ToFieldVector();
        
        ARROW_ASSIGN_OR_RAISE(auto reader, arrow::csv::TableReader::Make(
            arrow::io::default_io_context(), input_file, read_options, parse_options, convert_options));
        
        // Read table
        return reader->Read();
    }
    
    void process_tick_data(std::shared_ptr<arrow::Table> table, const std::string& schema_id) {
        auto start = std::chrono::high_resolution_clock::now();
        
        // Process each column
        for (int i = 0; i < table->num_columns(); ++i) {
            auto column = table->column(i);
            auto field = table->schema()->field(i);
            
            std::cout << "Processing column: " << field->name() << " (" << field->type()->ToString() << ")" << std::endl;
            
            // Here you would implement your low-latency processing logic
            // For example:
            // - Store in memory-mapped files
            // - Index for fast lookups
            // - Apply compression
            // - Update real-time analytics
        }
        
        processed_ticks_ += table->num_rows();
        
        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
        
        std::cout << "Processed " << table->num_rows() << " ticks in " 
                  << duration.count() << " microseconds" << std::endl;
    }
    
public:
    // Get performance statistics
    json get_stats() {
        auto now = std::chrono::steady_clock::now();
        auto runtime = std::chrono::duration_cast<std::chrono::seconds>(now - start_time_).count();
        
        auto schema_stats = schema_client_->get_stats();
        
        return {
            {"processed_ticks", processed_ticks_.load()},
            {"validation_errors", validation_errors_.load()},
            {"runtime_seconds", runtime},
            {"ticks_per_second", runtime > 0 ? processed_ticks_.load() / runtime : 0},
            {"schema_client", schema_stats},
            {"arrow_schemas_cached", arrow_schemas_.size()}
        };
    }
};

// Example usage
int main() {
    try {
        // Initialize Latency Tick Store
        LatencyTickStore tick_store("http://localhost:8000", "./data");
        tick_store.initialize();
        
        // Load tick data with schema validation
        bool success = tick_store.load_tick_data("data/ticks.csv", "ticks_v1");
        
        if (success) {
            std::cout << "Tick data loaded successfully!" << std::endl;
            
            // Get statistics
            auto stats = tick_store.get_stats();
            std::cout << "Performance Statistics:" << std::endl;
            std::cout << "  Processed ticks: " << stats["processed_ticks"] << std::endl;
            std::cout << "  Runtime: " << stats["runtime_seconds"] << " seconds" << std::endl;
            std::cout << "  Ticks/second: " << stats["ticks_per_second"] << std::endl;
            std::cout << "  Cache hit ratio: " << stats["schema_client"]["cache_hit_ratio"] << std::endl;
        } else {
            std::cerr << "Failed to load tick data" << std::endl;
            return 1;
        }
        
        // Keep running to monitor schema updates
        std::cout << "Monitoring for schema updates... (Press Ctrl+C to stop)" << std::endl;
        std::this_thread::sleep_for(std::chrono::seconds(300)); // 5 minutes
        
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
} 