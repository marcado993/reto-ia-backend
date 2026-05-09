import subprocess
import sys

def main():
    print("Downloading spaCy Spanish model...")
    subprocess.check_call([sys.executable, "-m", "spacy", "download", "es_core_news_md"])
    print("Done!")

if __name__ == "__main__":
    main()