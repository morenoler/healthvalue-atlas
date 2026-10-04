import argparse


def main():
    parser = argparse.ArgumentParser(description="HealthValue Atlas research pipeline")
    parser.add_argument("command", choices=["collect", "build", "serve"])
    args = parser.parse_args()
    if args.command == "collect":
        from .collect import main as collect

        collect()
    elif args.command == "build":
        from .models import main as models
        from .prepare import main as prepare
        from .publish import main as publish

        prepare()
        models()
        publish()
    else:
        import uvicorn

        uvicorn.run("healthvalue.api:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
