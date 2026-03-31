# Contributing

Thanks for your interest in Divergence Explorer! Contributions are welcome.

## Prerequisites

- Python 3.11+
- An [OpenGradient](https://opengradient.ai) wallet with OPG tokens ([faucet](https://faucet.opengradient.ai))
- Base Sepolia ETH for gas (~0.001 ETH, [faucet](https://www.alchemy.com/faucets/base-sepolia))

## Running from Source

```bash
git clone https://github.com/0xadvait/divergence-explorer.git
cd divergence-explorer
pip install opengradient rich numpy
export OG_PRIVATE_KEY=your_private_key_here
python -m src.explorer
```

## Submitting Changes

1. Fork the repo and create a feature branch from `main`.
2. Make your changes. Keep PRs focused on a single concern.
3. Test locally — run the explorer for at least a few iterations and confirm the dashboard generates cleanly.
4. Open a pull request with a clear description of what changed and why.

## Reporting Issues

Open a [GitHub issue](https://github.com/0xadvait/divergence-explorer/issues) with:
- What you expected to happen
- What actually happened
- Steps to reproduce

## Code Style

- Keep it simple. No unnecessary abstractions.
- Follow existing patterns in `src/`.
- Use type hints where practical.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
