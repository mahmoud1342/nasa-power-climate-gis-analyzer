# Publishing on GitHub

## License (MIT) - what it means
Anyone may use, copy, modify, distribute and even sell the software, including in closed-source
products, as long as the copyright notice and license text are kept. There is no warranty.
Alternatives: Apache-2.0 (like MIT plus an explicit patent grant) or GPL-3.0 (derivatives must stay
open source). MIT was chosen for maximum adoption.

## Steps
1. Check `src/npcga/config.py`: developer name and LinkedIn link (open the link in a browser first).
2. Create an empty public repository on GitHub (no README, no license: they already exist).
3. In the project folder:
```
git init
git add .
git commit -m "NASA POWER Climate & GIS Analyzer v0.1.0"
git branch -M main
git remote add origin https://github.com/<your-user>/<repo-name>.git
git push -u origin main
```
4. Replace `<repository-url>` in `README.md` with the real address; add real screenshots to
   `docs/images/` and link them in the README.
5. Open the "Actions" tab and confirm the tests pass on Windows and Ubuntu.
6. Create a release: tag `v0.1.0`, paste the `CHANGELOG.md` section.
7. Optional: connect the repository to Zenodo to get a DOI and add it to `CITATION.cff`.

## Before you push
- `git status` must not list `outputs/`, `.venv/` or any personal data (they are in `.gitignore`).
- No API keys exist in this project; keep it that way.
