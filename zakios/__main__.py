"""Interface en ligne de commande : python3 -m zakios build | verify."""
import argparse
import sys

from .build import BuildError, ValidationError, build, validate_catalog


def main(argv=None):
    parser = argparse.ArgumentParser(prog="zakios", description="Catalogue ZakiOS")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="générer le catalogue à partir du manifeste de sources")
    b.add_argument("--manifest", default="sources.json")
    b.add_argument("--sources-root", default="sources", help="dossier contenant les dépôts clonés (<owner>/<repo>)")
    b.add_argument("--out", default="catalog")
    b.add_argument("--decisions", default="decisions/validated.json")
    b.add_argument("--allow-dirty", action="store_true", help="accepter des modifications locales dans les sources")

    v = sub.add_parser("verify", help="valider un catalogue généré")
    v.add_argument("--catalog", default="catalog")

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            report = build(args.manifest, args.sources_root, args.out,
                           allow_dirty=args.allow_dirty, decisions_path=args.decisions)
            total = sum(report["counts_by_type"].values())
            print("Catalogue généré : %d composants, %d problèmes de métadonnées signalés, %d validations périmées."
                  % (total, len(report["metadata_issues"]), len(report["stale_decisions"])))
            if report["build_mode"] != "exact":
                print("ATTENTION : génération EXPÉRIMENTALE, sources modifiées localement (%s). "
                      "Ce n'est pas une reconstruction exacte des commits." % ", ".join(report["dirty_sources"]))
        else:
            info = validate_catalog(args.catalog)
            print("Catalogue valide : %(components)d composants, %(evaluated)d évalués, mode %(build_mode)s." % info)
    except (BuildError, ValidationError) as exc:
        print("ERREUR : %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
