#!/usr/bin/env python3
"""Generate Hugo pages for every Bicep module published in the Innofactor registry.

Reads only what the registry publishes (anonymous pull). Nothing is read from the
internal source repository.

Content sources per module, in order of preference:
  1. A docs artefact `docs/<module>:<version>` holding README.md and CHANGELOG.md
     layers (pushed by the module publish pipeline, e.g. with `oras push`).
  2. The module artefact itself: the description annotation (the module README
     intro) and the compiled ARM template (parameters, outputs).

The module index is validated against the registry catalog. Drift fails the build.
"""
import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

REGISTRY = os.environ.get("MODULE_REGISTRY", "piacbicepregistryacr.azurecr.io")
SCHEME = os.environ.get("MODULE_REGISTRY_SCHEME", "https")
DOCS_PREFIX = "docs/"
GUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
ZERO_GUID = "00000000-0000-0000-0000-000000000000"
MANIFEST_ACCEPT = "application/vnd.oci.image.manifest.v1+json"
BICEP_SOURCE_LAYER = "application/vnd.ms.bicep.module.layer.v1+json"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(NoRedirect)
_tokens = {}


def http(url, headers=None):
    """GET with manual redirect handling. Auth is dropped on cross-host redirects."""
    headers = dict(headers or {})
    for _ in range(5):
        req = urllib.request.Request(url, headers=headers)
        try:
            with _opener.open(req, timeout=60) as r:
                return r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                nxt = urllib.parse.urljoin(url, e.headers["Location"])
                if urllib.parse.urlparse(nxt).netloc != urllib.parse.urlparse(url).netloc:
                    headers.pop("Authorization", None)
                url = nxt
                continue
            return e.code, e.read(), e.headers
    raise RuntimeError("too many redirects: " + url)


def token(scope):
    if scope not in _tokens:
        q = urllib.parse.urlencode({"scope": scope, "service": REGISTRY})
        code, body, _ = http(f"{SCHEME}://{REGISTRY}/oauth2/token?{q}")
        if code != 200:
            sys.exit(f"ERROR: anonymous token for {scope} refused (HTTP {code})")
        _tokens[scope] = json.loads(body)["access_token"]
    return _tokens[scope]


def reg_get(path, scope, accept=None):
    h = {"Authorization": "Bearer " + token(scope)}
    if accept:
        h["Accept"] = accept
    return http(f"{SCHEME}://{REGISTRY}/v2/{path}", h)


def catalog():
    repos, path = [], "_catalog?n=1000"
    code, body, _ = reg_get(path, "registry:catalog:*")
    if code != 200:
        sys.exit(f"ERROR: registry catalog not readable anonymously (HTTP {code})")
    repos = json.loads(body)["repositories"]
    return sorted(r for r in repos if r.startswith("avm/"))


def semver_key(v):
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$", v)
    if not m:
        return None
    return (int(m[1]), int(m[2]), int(m[3]), 1 if m[4] is None else 0, m[4] or "")


def tags(repo):
    code, body, _ = reg_get(f"{repo}/tags/list", f"repository:{repo}:pull")
    if code != 200:
        sys.exit(f"ERROR: tags/list for {repo} failed (HTTP {code})")
    ts = [t for t in (json.loads(body).get("tags") or []) if semver_key(t)]
    return sorted(ts, key=semver_key)


def manifest(repo, ref):
    code, body, _ = reg_get(f"{repo}/manifests/{ref}", f"repository:{repo}:pull", MANIFEST_ACCEPT)
    return json.loads(body) if code == 200 else None


def blob(repo, digest):
    code, body, _ = reg_get(f"{repo}/blobs/{digest}", f"repository:{repo}:pull")
    if code != 200:
        sys.exit(f"ERROR: blob {digest} of {repo} failed (HTTP {code})")
    return body


def docs_artefact(repo, version):
    """Return {'README.md': text, 'CHANGELOG.md': text} from docs/<repo>:<version>, or {}."""
    m = manifest(DOCS_PREFIX + repo, version)
    if not m:
        return {}
    out = {}
    for layer in m.get("layers", []):
        name = (layer.get("annotations") or {}).get("org.opencontainers.image.title", "")
        if name in ("README.md", "CHANGELOG.md"):
            out[name] = blob(DOCS_PREFIX + repo, layer["digest"]).decode("utf-8")
    return out


def arm_template(m, repo):
    for layer in m.get("layers", []):
        if layer["mediaType"] == BICEP_SOURCE_LAYER:
            return json.loads(blob(repo, layer["digest"]))
    return {}


def cell(text):
    text = (text or "").strip()
    text = re.sub(r"\s*\n\s*", "<br>", text)
    return text.replace("|", "\\|")


def type_name(p, defs):
    if "$ref" in p:
        name = p["$ref"].split("/")[-1]
        d = defs.get(name, {})
        return f"`{name}` ({d.get('type', 'object')})"
    t = p.get("type", "")
    return f"`{t}`" if t else ""


def param_table(items, defs, outputs=False):
    if not items:
        return "_None._\n"
    if outputs:
        rows = ["| Name | Type | Description |", "| --- | --- | --- |"]
        for n, p in sorted(items.items()):
            rows.append(f"| `{n}` | {type_name(p, defs)} | {cell((p.get('metadata') or {}).get('description'))} |")
    else:
        rows = ["| Name | Type | Required | Default | Description |", "| --- | --- | --- | --- | --- |"]
        for n, p in sorted(items.items(), key=lambda kv: ("defaultValue" in kv[1] or kv[1].get("nullable", False), kv[0])):
            req = "No" if ("defaultValue" in p or p.get("nullable")) else "Yes"
            dv = json.dumps(p["defaultValue"]) if "defaultValue" in p else ""
            dv = GUID_RE.sub("<guid>", dv)  # defaults can carry vendor rule ids; never publish id-shaped values
            if len(dv) > 60:
                dv = dv[:57] + "..."
            rows.append(
                f"| `{n}` | {type_name(p, defs)} | {req} | {('`' + cell(dv) + '`') if dv else ''} "
                f"| {cell((p.get('metadata') or {}).get('description'))} |"
            )
    return "\n".join(rows) + "\n"


def demote(md, by=2):
    """Push markdown headings down so a README H1 sits under the page's own section heading."""
    out, fenced = [], False
    for line in md.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        if not fenced and re.match(r"^#{1,6}\s", line):
            line = "#" * by + line
            line = re.sub(r"^(#{7,})", "######", line)
        out.append(line)
    return "\n".join(out)


def text_so_far(body):
    return "\n".join(body)


def slug(repo):
    return repo[len("avm/"):].replace("/", "-")


def read_csv_index(static_dir):
    rows = []
    for fn in ("BicepPatternModules.csv", "BicepResourceModules.csv", "BicepUtilityModules.csv"):
        path = os.path.join(static_dir, fn)
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                r["_file"] = fn
                rows.append(r)
    return rows


def check_drift(cat, rows):
    """Return a list of drift messages. Only rows that point at the Innofactor registry count."""
    ours = [r for r in rows if r["PublicRegistryReference"].startswith("br/innofactor:")]
    available = {r["ModuleName"] for r in ours if r["ModuleStatus"].startswith(("Available", "Orphaned"))}
    deprecated = {r["ModuleName"] for r in ours if r["ModuleStatus"].startswith("Deprecated")}
    listed = {r["ModuleName"] for r in ours}
    cat = set(cat)
    msgs = []
    for m in sorted(cat - listed):
        msgs.append(f"in registry but missing from the CSV indexes: {m}")
    for m in sorted((cat & listed) - available - deprecated):
        msgs.append(f"in registry but not marked Available in the CSV: {m}")
    for m in sorted(available - cat):
        msgs.append(f"marked Available in the CSV but not in the registry: {m}")
    return msgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs", help="Hugo site directory")
    ap.add_argument("--no-drift-fail", action="store_true", help="report drift but do not fail")
    ap.add_argument("--only", help="generate only this module (testing)")
    a = ap.parse_args()

    out_dir = os.path.join(a.docs, "content", "modules")
    data_dir = os.path.join(a.docs, "data")
    static_dir = os.path.join(a.docs, "static", "module-indexes")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    cat = catalog()
    rows = read_csv_index(static_dir)
    names = {r["ModuleName"]: r["ModuleDisplayName"] or r.get("ResourceType", "") for r in rows}
    deprecations = {r["ModuleName"]: r["Comments"] for r in rows if r["ModuleStatus"].startswith("Deprecated")}
    drift = check_drift(cat, rows)
    for d in drift:
        print("DRIFT:", d, file=sys.stderr)

    registry_data, problems, now = {}, [], datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for repo in cat:
        if a.only and repo != a.only:
            continue
        vs = tags(repo)
        if not vs:
            problems.append(f"{repo}: no semver tags")
            continue
        latest = vs[-1]
        mf = manifest(repo, latest)
        ann = (mf or {}).get("annotations", {})
        history = []
        for v in reversed(vs):
            mv = manifest(repo, v) or {}
            history.append((v, (mv.get("annotations") or {}).get("org.opencontainers.image.created", "")[:10]))
        docs = docs_artefact(repo, latest)
        arm = arm_template(mf, repo) if mf else {}
        defs = arm.get("definitions", {})
        desc = (arm.get("metadata", {}).get("description") or ann.get("org.opencontainers.image.description") or "").strip()
        title = names.get(repo) or repo
        body = [
            "---",
            f"title: \"{title}\"",
            f"linktitle: \"{repo}\"",
            f"description: \"Published Bicep module {repo}, latest version {latest}\"",
            "---",
            "",
            f"`br/innofactor:{repo}:{latest}`",
            "",
        ]
        if repo in deprecations:
            body += [f"> **Deprecated.** {deprecations[repo]} Published versions remain available in the registry.", ""]
        if "README.md" in docs:
            body += ["## README", "", demote(docs["README.md"].strip()), ""]
            source = "docs artefact"
        else:
            body += ["## Overview", "", desc or "_No description published for this module._", ""]
            source = "module artefact"
            if arm:
                body += [
                    "## Parameters", "", param_table(arm.get("parameters"), defs),
                    "## Outputs", "", param_table(arm.get("outputs"), defs, outputs=True),
                ]
        body += ["## Changelog", ""]
        if "CHANGELOG.md" in docs:
            body += [demote(docs["CHANGELOG.md"].strip()), ""]
        else:
            body += ["_No changelog has been published for this module yet. See the version history below._", ""]
        body += ["## Version history", "", "| Version | Published |", "| --- | --- |"]
        body += [f"| `{v}` | {d or 'n/a'} |" for v, d in history]
        if "```bicep" not in text_so_far(body):
            body += ["", "## Use this module", "", "```bicep",
                     f"module example 'br/innofactor:{repo}:{latest}' = {{", "  name: 'example'", "  params: {}", "}", "```"]
        body += [""]
        text = "\n".join(body)
        bad = [g for g in GUID_RE.findall(text) if g != ZERO_GUID]
        if bad:
            problems.append(f"{repo}: published content contains GUID-like values {sorted(set(bad))}; refusing to publish them on the public site")
            continue
        with open(os.path.join(out_dir, slug(repo) + ".md"), "w", encoding="utf-8") as f:
            f.write(text)
        registry_data[repo] = {"slug": slug(repo), "latest": latest, "versions": [v for v, _ in history], "source": source}
        print(f"OK   {repo} {latest} ({source}) -> content/modules/{slug(repo)}.md")

    index = ["---", "title: \"Published modules\"", "linktitle: \"Published modules\"", "type: default", "weight: 3",
             "description: \"Bicep modules published in the Innofactor registry\"", "---", "",
             f"Generated from the registry catalog on {now}.", "",
             "| Module | Latest | Versions |", "| --- | --- | --- |"]
    for repo, d in registry_data.items():
        index.append(f"| [{repo}]({d['slug']}/) | `{d['latest']}` | {len(d['versions'])} |")
    with open(os.path.join(out_dir, "_index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    with open(os.path.join(data_dir, "registry.json"), "w", encoding="utf-8") as f:
        json.dump(registry_data, f, indent=2, sort_keys=True)

    for p in problems:
        print("ERROR:", p, file=sys.stderr)
    if problems or (drift and not a.no_drift_fail):
        sys.exit(1)


if __name__ == "__main__":
    main()
