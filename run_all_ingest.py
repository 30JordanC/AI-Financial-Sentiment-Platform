import subprocess

scripts = [
    "company_descriptions.py",
    "financials_ingest.py",
    "price_history_ingest.py",
    "polygon_news.py",
    "whats_happening_ingest.py"
]

for script in scripts:
    print(f"\n--- Running {script} ---")
    result = subprocess.run(
        ["python", script],
        cwd="polygonapitesting/src/app/",
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print("ERROR:", result.stderr) 