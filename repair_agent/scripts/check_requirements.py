import sys
from importlib.metadata import PackageNotFoundError, version
from packaging.requirements import Requirement


def _package_version(name: str) -> str | None:
    for candidate in (name, name.replace("-", "_"), name.replace("_", "-")):
        try:
            return version(candidate)
        except PackageNotFoundError:
            continue
    return None


def main():
    requirements_file = sys.argv[1]
    with open(requirements_file, "r", encoding="utf-8") as handle:
        required_packages = [
            line.strip().split("#")[0].strip() for line in handle.readlines()
        ]

    missing_packages = []
    for required_package in required_packages:
        if not required_package:
            continue
        req = Requirement(required_package)
        installed_version = _package_version(req.name)
        if installed_version is None or installed_version not in req.specifier:
            missing_packages.append(str(req))

    if missing_packages:
        print("Missing packages:")
        print(", ".join(missing_packages))
        sys.exit(1)

    print("All packages are installed.")


if __name__ == "__main__":
    main()
