# Contributing Guidelines

Thank you for considering contributing to our project! Please follow these steps to help us maintain project quality.

## Code of Conduct

Please review our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

## How to Contribute

### Reporting Bugs

- Use GitHub Issues to report bugs.
- Provide clear steps to reproduce the issue.
- Include environment details and any error messages.

### Proposing Enhancements

- Open an issue to discuss the idea first.
- If approved, submit a pull request with your changes.

### Pull Request Guidelines

- Ensure your code follows our formatting and documentation standards.
- Write unit tests for new features or bug fixes.
- Focus on a single goal per pull request.
- Use descriptive commit messages.

## Development Setup

1. Fork the repository.
2. Clone and install in development mode:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Snatch.git
   cd Snatch
   pip install -e ".[dev,all]"
   ```
3. Run the test suite:
   ```bash
   python -m pytest tests/ -v
   ```
4. Format your code:
   ```bash
   black snatch/ tests/
   isort --profile black snatch/ tests/
   ```
5. Create a branch for your feature or bug fix.
6. Commit your changes with clear messages.
7. Push to your fork and create a pull request.

## Communication

Feel free to join discussions on our GitHub Issues or project chat channels.

Thank you for your contributions!
