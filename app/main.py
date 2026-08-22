from dotenv import load_dotenv
from app.pipeline import run_pipeline


def main():
    load_dotenv()
    print("AI News API starter project is running!")
    print(run_pipeline().model_dump_json(indent=2))

if __name__ == '__main__':
    main()