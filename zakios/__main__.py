"""Interface en ligne de commande : python3 -m zakios build | verify."""
import argparse
import sys

import json

from . import activate, deliver
from .build import BuildError, ValidationError, build, validate_catalog


def main(argv=None):
    parser = argparse.ArgumentParser(prog="zakios", description="Catalogue ZakiOS")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="générer le catalogue à partir du manifeste de sources")
    b.add_argument("--manifest", default="sources.json")
    b.add_argument("--sources-root", default="sources", help="dossier contenant les dépôts clonés (<owner>/<repo>)")
    b.add_argument("--out", default="catalog")
    b.add_argument("--decisions", default="decisions/validated.json")
    b.add_argument("--licenses", default="decisions/licenses.json", help="licences vérifiées par un humain")
    b.add_argument("--annotations", default="decisions/annotations.json", help="dépendances, conflits, compatibilité")
    b.add_argument("--allow-dirty", action="store_true", help="accepter des modifications locales dans les sources")

    for name, text in (("plan", "aperçu exact de l'installation (n'écrit rien)"),
                       ("apply", "installer la sélection dans un projet (tout ou rien)")):
        a = sub.add_parser(name, help=text)
        a.add_argument("--project", required=True)
        a.add_argument("--profile", help="fichier de sélection (défaut : <projet>/.zakios/profile.json)")
        a.add_argument("--catalog", default="catalog")
        a.add_argument("--sources-root", default="sources")
        a.add_argument("--json", action="store_true", help="sortie JSON (plan)")
        if name == "apply":
            a.add_argument("--plan-sha", help="empreinte lue dans l'aperçu ; refuse si le plan a changé")
    sp = sub.add_parser("save-plan", help="enregistrer un plan sous docs/plans/ (aperçu avec --preview, puis --sha)")
    sp.add_argument("--project", required=True)
    sp.add_argument("--path", required=True, help="chemin proposé, ex. docs/plans/2026-10-26-sujet.md")
    sp.add_argument("--content-file", required=True, help="fichier contenant le plan (lu comme texte, jamais exécuté)")
    sp.add_argument("--preview", action="store_true", help="afficher chemin et empreinte, sans écrire")
    sp.add_argument("--sha", help="empreinte de livraison lue dans l'aperçu ; obligatoire pour enregistrer")
    sp.add_argument("--mission", default="", help="mission à laquelle le livrable se rattache")
    r = sub.add_parser("rollback", help="annuler la dernière installation")
    r.add_argument("--project", required=True)

    v = sub.add_parser("verify", help="valider un catalogue généré")
    v.add_argument("--catalog", default="catalog")

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            report = build(args.manifest, args.sources_root, args.out,
                           allow_dirty=args.allow_dirty, decisions_path=args.decisions,
                           licenses_path=args.licenses, annotations_path=args.annotations)
            total = sum(report["counts_by_type"].values())
            print("Catalogue généré : %d composants, %d problèmes de métadonnées signalés, %d validations périmées."
                  % (total, len(report["metadata_issues"]), len(report["stale_decisions"])))
            if report["build_mode"] != "exact":
                print("ATTENTION : génération EXPÉRIMENTALE, sources modifiées localement (%s). "
                      "Ce n'est pas une reconstruction exacte des commits." % ", ".join(report["dirty_sources"]))
        elif args.command in ("plan", "apply"):
            selection = activate.load_profile(args.project, args.profile)
            if args.command == "plan":
                result = activate.plan(args.project, args.catalog, args.sources_root, selection)
                result.pop("_contents")
                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True))
                else:
                    for act in result["actions"]:
                        print("%-9s %s  (%s)" % (act["action"], act["path"], act["component_id"]))
                    for ref in result["refused"]:
                        print("REFUSÉ    %s : %s" % (ref["component_id"], "; ".join(ref["reasons"])))
                    for note in result["notes"]:
                        print("NOTE      " + note)
                    print("plan_sha256 : " + result["plan_sha256"])
                return 1 if result["refused"] else 0
            out = activate.apply(args.project, args.catalog, args.sources_root, selection, expected_plan=args.plan_sha)
            print("Installation : %(applied)d fichier(s) écrit(s), %(unchanged)d inchangé(s), transaction %(transaction)s." % out)
        elif args.command == "save-plan":
            with open(args.content_file, "rb") as handle:
                content = handle.read()
            if args.preview:
                info = deliver.preview(args.path, content, args.mission)
                print("Aperçu : %(path)s, %(bytes)d octets, contenu %(content_sha256)s, livraison %(delivery_sha256)s (rien n'est écrit)." % info)
            else:
                if not args.sha:
                    raise deliver.DeliveryError("--sha obligatoire : relis l'aperçu (--preview) puis fournis l'empreinte de livraison")
                out = deliver.save_plan(args.project, args.path, content, args.sha, mission=args.mission)
                print("%(status)s : %(path)s (livraison %(delivery_sha256)s), trace %(trace)s." % out)
        elif args.command == "rollback":
            out = activate.rollback(args.project)
            print("Retour arrière effectué : transaction %s annulée." % out["transaction"])
        else:
            info = validate_catalog(args.catalog)
            print("Catalogue valide : %(components)d composants, %(evaluated)d évalués, mode %(build_mode)s." % info)
    except (BuildError, ValidationError, activate.ActivationError) as exc:
        print("ERREUR : %s" % exc, file=sys.stderr)
        for reason in getattr(exc, "reasons", []):
            print("  - " + reason, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
