# Releasing fraudnova-python

These are your steps to publish the package. The code, tests and docs are already committed on `main`.

## First release (1.0.0)

1. Create the empty public repository `dahleedam/fraudnova-python` on GitHub (no README, no licence, no .gitignore).
2. Push `main`:

   ```bash
   git remote add origin git@github.com:dahleedam/fraudnova-python.git
   git push -u origin main
   ```

3. Open https://github.com/dahleedam/fraudnova-python/actions and wait for the **CI** run to go green on every Python version (3.9 to 3.13) and the build job. Do not tag until it is green.
4. On PyPI, go to **Account settings → Publishing** and click **Add a new pending publisher**. Enter:
   - PyPI project name: `fraudnova`
   - Owner: `dahleedam`
   - Repository name: `fraudnova-python`
   - Workflow name: `release.yml`
   - Environment name: `pypi`

   A pending publisher lets the first release create the project; no API token is needed.
5. On GitHub, go to **Settings → Environments** and create an environment named `pypi`. Optionally restrict it to tags matching `v*`.
6. Tag the release and push the tag:

   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

   The **Release** workflow builds the package, publishes it to PyPI through Trusted Publishing, and creates the GitHub release with generated notes.
7. Check that the package installs in an empty virtual environment:

   ```bash
   python -m venv /tmp/fn && /tmp/fn/bin/pip install fraudnova && /tmp/fn/bin/python -c "import fraudnova; print(fraudnova.__version__)"
   ```

## Follow-ups in the other repositories (separate session)

- Main app: add a "Python SDK" install line (`pip install fraudnova`) with a link to the GitHub repository on `/docs`.
- Main app: add a changelog entry for the Python SDK on `/admin/changelog`.
- Examples repository: link the SDK from the README of `dahleedam/fraudnova-examples`.

## Patch and minor releases

1. Make the change on `main` with tests.
2. Bump `__version__` in `src/fraudnova/_version.py` (it is sent in the `User-Agent` header and read by the build).
3. In `CHANGELOG.md`, move the entries under `## [Unreleased]` into a new section such as `## [1.0.1] - YYYY-MM-DD`, and add its link reference at the bottom.
4. Commit, push, wait for CI to go green, then tag and push the tag:

   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```

   The Release workflow publishes to PyPI and creates the GitHub release.

## Rules

Nothing public (README, changelog, docs, code, commit messages) may name the upstream data provider or describe keys, credentials or quota internals.

The leak-guard test (`tests/test_leak_guard.py`) runs on every push. It only catches the provider's name or abbreviation and two fixed phrases in tracked files. It does not read commit messages, and it cannot tell when text describes keys or quota internals in other words, so check those by hand before you push.

`tests/test_release_consistency.py` fails when `__version__` differs from the newest version heading in `CHANGELOG.md`, so bump both together.
