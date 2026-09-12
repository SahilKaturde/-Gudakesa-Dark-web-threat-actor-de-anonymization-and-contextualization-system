import os

def main():
    print("Hello from backend!")


if __name__ == "__main__":
    main()

os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["ALL_PROXY"] = ""