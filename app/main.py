from app.pipeline import run_pipeline

def main():
    print("AI News API starter project is running!")

    for item in run_pipeline():
        print(item)

if __name__ == '__main__':
    main()