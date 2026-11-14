import argparse
from app.config import settings
from app.repositories.documents import indexes
from app.services.career import setup_checkpoints


def main():
    parser = argparse.ArgumentParser(
        description="Explicit operator setup; never invoked automatically in hosted startup"
    )
    parser.add_argument("command", choices=["indexes", "checkpoints", "dispatch", "recover"])
    command = parser.parse_args().command
    if command == "indexes":
        indexes()
    elif command == "checkpoints":
        setup_checkpoints()
    elif command == "dispatch":
        from app.services.jobs import dispatch

        dispatch()
    elif command == "recover":
        from app.services.jobs import recover

        recover()
    print(f"{command}: completed ({settings.environment})")


if __name__ == "__main__":
    main()
