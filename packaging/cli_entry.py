from clipoteca.cli import main
from clipoteca.windows_path import refresh_windows_user_path


if __name__ == "__main__":
    refresh_windows_user_path()
    raise SystemExit(main())
