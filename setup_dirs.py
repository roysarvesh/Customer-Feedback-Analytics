"""Setup script — creates all project directories and placeholder files."""
import pathlib

base = pathlib.Path(__file__).parent

dirs = [
    "assets",
    "data/raw",
    "data/processed",
    "data/database",
    "notebooks",
    "sql",
    "tests",
    ".streamlit",
    "src",
    "dashboard",
]

for d in dirs:
    (base / d).mkdir(parents=True, exist_ok=True)
    print(f"OK: {base / d}")

# gitkeeps
for gk in ["data/raw", "data/processed", "data/database", "assets"]:
    p = base / gk / ".gitkeep"
    p.touch()

# Streamlit config
cfg_content = (
    '[theme]\n'
    'primaryColor = "#6C63FF"\n'
    'backgroundColor = "#0E1117"\n'
    'secondaryBackgroundColor = "#1A1D2E"\n'
    'textColor = "#EAEAEA"\n'
    'font = "sans serif"\n\n'
    '[server]\n'
    'maxUploadSize = 200\n\n'
    '[browser]\n'
    'gatherUsageStats = false\n'
)
(base / ".streamlit" / "config.toml").write_text(cfg_content, encoding="utf-8")
print("Streamlit config.toml written.")
print("All directories created successfully.")
