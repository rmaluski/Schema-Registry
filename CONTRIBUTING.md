# Contributing to Schema Registry

Thank you for your interest in contributing to the Schema Registry project! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

### Local Development

1. **Clone the repository**

   ```bash
   git clone https://github.com/rmaluski/Schema-Registry.git
   cd Schema-Registry
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Start development environment**

   ```bash
   make start-dev
   ```

4. **Run tests**
   ```bash
   make test
   ```

## Code Style

We use the following tools to maintain code quality:

- **Black**: Code formatting
- **isort**: Import sorting
- **mypy**: Type checking
- **pytest**: Testing

Run the following commands before submitting a PR:

```bash
make format  # Format code
make lint    # Check code quality
make test    # Run tests
```

## Schema Development

### Creating New Schemas

1. **Create schema file** in `schemas/` directory

   ```json
   {
     "id": "your_schema_name",
     "schema": "http://json-schema.org/draft-07/schema#",
     "title": "Your Schema Title",
     "type": "object",
     "properties": {
       "field1": { "type": "string" },
       "field2": { "type": "integer" }
     },
     "required": ["field1"],
     "version": "1.0.0"
   }
   ```

2. **Validate schema**

   ```bash
   python scripts/validate_all.py schemas/
   ```

3. **Test compatibility**
   ```bash
   python scripts/diff_schemas.py <old_version> <new_version>
   ```

### Schema Evolution Rules

- **Compatible changes**: Add optional fields, widen types, add enum values
- **Breaking changes**: Remove fields, narrow types, remove enum values
- **Version bumping**: Breaking changes require major version bump

## Pull Request Process

1. **Create a feature branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**

   - Follow the code style guidelines
   - Add tests for new functionality
   - Update documentation if needed

3. **Test your changes**

   ```bash
   make all  # Runs install, format, lint, and test
   ```

4. **Submit a pull request**
   - Provide a clear description of changes
   - Reference any related issues
   - Ensure CI checks pass

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_validation.py

# Run with coverage
pytest --cov=app tests/
```

### Writing Tests

- Place tests in the `tests/` directory
- Use descriptive test names
- Test both success and failure cases
- Mock external dependencies

## Documentation

### Updating Documentation

- Update `README.md` for user-facing changes
- Update `docs/ARCHITECTURE.md` for architectural changes
- Add inline documentation for complex functions

### API Documentation

The API documentation is automatically generated from FastAPI docstrings. Update the docstrings in `app/main.py` to improve the generated documentation.

## Release Process

### Creating a Release

1. **Update version** in `app/config.py`
2. **Update CHANGELOG.md** with release notes
3. **Create a release tag**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

### Release Checklist

- [ ] All tests pass
- [ ] Documentation is updated
- [ ] Version is bumped
- [ ] CHANGELOG is updated
- [ ] Release notes are written

## Issues and Bug Reports

### Reporting Bugs

When reporting bugs, please include:

- Description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)
- Error messages and stack traces

### Feature Requests

When requesting features, please include:

- Description of the feature
- Use case and motivation
- Proposed implementation approach
- Impact on existing functionality

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project.

## Questions?

If you have questions about contributing, please:

1. Check the existing documentation
2. Search existing issues
3. Create a new issue with the "question" label

Thank you for contributing to Schema Registry!
