"""
OpenWiki 위키 생성 준비와 결과 수집

OpenWiki(https://github.com/langchain-ai/openwiki)는 "현재 git 저장소"를 읽어 openwiki/ 에
위키를 쓰는 CLI다. 원본 스냅샷(data/raw/fastapi)에서 바로 돌리면 원본 안에 openwiki/ 가
생기고, 코퍼스 밖의 fastapi/ 패키지·tests/·번역 문서까지 문서화한다.
그래서 코퍼스 문서만 같은 상대 경로로 복사한 별도 git 저장소를 만들고 거기서 실행한다.

    data/openwiki/
      INSTRUCTIONS.md              위키 작성 지침 (버전 관리). work/openwiki/ 로 복사됨
      openwiki.env.example         OpenWiki 설정 예시 -> config/.env 로 복사해 채움
      config/                      OPENWIKI_CONFIG_DIR (.env 등, 버전 관리 제외)
      work/                        OpenWiki 를 실행할 폴더 (git 저장소, 버전 관리 제외)
        docs/en/docs/**/*.md       코퍼스 문서 (config.corpus_exclude 적용)
        docs_src/**/*.py 등        코퍼스 코드 (문서가 참조하는 fastapi/openapi/docs.py 포함)
        SOURCE.md, corpus.json     스냅샷 커밋, 코퍼스 매니페스트 해시
        openwiki/                  <- OpenWiki 출력
      wiki_v0/                     --collect 로 고정한 위키 (버전 관리, 팀 공유용)
      wiki_v0.meta.json            생성 모델, 페이지 수, 토큰, 원본 문서 커버리지

파일은 원본 그대로 복사하고, 경로도 doc_id(저장소 루트 기준) 그대로 둔다.
INSTRUCTIONS.md 가 위키 페이지마다 "## Sources" 에 원본 doc_id 를 적게 하므로,
--collect 가 이를 읽어 위키 페이지 -> 원본 문서 대응표와 커버리지를 만든다.

사용법
    python src/openwiki_prep.py                    # 작업 폴더 생성 (이미 있으면 중단)
    python src/openwiki_prep.py --force            # 작업 폴더를 지우고 다시 생성
    (PowerShell) $env:OPENWIKI_CONFIG_DIR = "<token_lab>/data/openwiki/config"
                 cd data/openwiki/work; openwiki --init
    python src/openwiki_prep.py --collect          # work/openwiki -> wiki_v0 + 메타
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from config import CFG
from corpus import load_corpus, manifest_sha256
from llm import count_tokens

BASE = CFG.root / "data" / "openwiki"
WORK_DIR = BASE / "work"
CONFIG_DIR = BASE / "config"
INSTRUCTIONS = BASE / "INSTRUCTIONS.md"
# 수집 대상에서 뺄 OpenWiki 실행 상태 파일
RUN_STATE = {".run.json", ".last-update.json"}

SOURCE_MD = """# Source snapshot

This repository is a copy of the documentation corpus of FastAPI, taken from
the official repository without modification.

- upstream: https://github.com/fastapi/fastapi
- snapshot: {source}
- corpus manifest sha256: {sha}
- documents: {n_doc} markdown pages under docs/en/docs, {n_code} code files

Markdown pages include example code with `{{* path/to/file.py *}}` references.
The referenced file exists at that path relative to the page (or relative to the
repository root after stripping leading `../`). `ln[a:b]` selects lines a..b
(1-based, inclusive) and `hl[...]` only highlights lines.
"""

SOURCES_HEADING = re.compile(r"^##\s+Sources\s*$", re.M)
SOURCE_PATH = re.compile(r"(docs/en/docs/\S+?\.md)")


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          check=True).stdout.strip()


def _rmtree(path: Path):
    shutil.rmtree(path, onerror=lambda f, p, _: (Path(p).chmod(0o700), f(p)))


def build(force: bool) -> Path:
    if WORK_DIR.exists():
        if not force:
            raise SystemExit(f"이미 있습니다: {WORK_DIR}\n다시 만들려면 --force "
                             "(openwiki/ 출력도 함께 지워집니다)")
        _rmtree(WORK_DIR)

    corpus = load_corpus()
    sha = manifest_sha256(corpus)
    for d in corpus:
        dst = WORK_DIR / d.doc_id
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CFG.raw_repo / d.doc_id, dst)

    n_doc, n_code = len(corpus.docs("doc")), len(corpus.docs("code"))
    (WORK_DIR / "SOURCE.md").write_text(
        SOURCE_MD.format(source=corpus.source, sha=sha, n_doc=n_doc, n_code=n_code),
        encoding="utf-8", newline="\n")
    (WORK_DIR / "corpus.json").write_text(json.dumps(
        {"source": corpus.source, "corpus_manifest_sha256": sha,
         "documents": n_doc, "code_files": n_code}, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    # OpenWiki 는 --init 때도 openwiki/INSTRUCTIONS.md 를 보존하고 지침으로 읽는다
    (WORK_DIR / "openwiki").mkdir()
    shutil.copyfile(INSTRUCTIONS, WORK_DIR / "openwiki" / "INSTRUCTIONS.md")

    # OpenWiki 는 git diff 로 변경을 추적하므로 첫 커밋을 만들어 둔다
    git("init", "-q", cwd=WORK_DIR)
    git("add", "-A", cwd=WORK_DIR)
    git("-c", "user.name=token_lab", "-c", "user.email=token_lab@localhost",
        "commit", "-q", "-m", f"corpus snapshot {corpus.source}", cwd=WORK_DIR)
    CONFIG_DIR.mkdir(exist_ok=True)

    print(f"작업 폴더: {WORK_DIR}")
    print(f"  문서 {n_doc}개, 코드 {n_code}개, 매니페스트 {sha[:12]}")
    print(f"  스냅샷 {corpus.source}")
    if not (CONFIG_DIR / ".env").is_file():
        print(f"\n다음: {BASE / 'openwiki.env.example'} 를 {CONFIG_DIR / '.env'} 로 복사해 채우기")
    return WORK_DIR


# ---------------- 결과 수집 ----------------

def page_sources(text: str) -> list[str]:
    """페이지 끝 "## Sources" 섹션의 doc_id 목록 (등장 순, 중복 제거)."""
    m = SOURCES_HEADING.search(text)
    if not m:
        return []
    return list(dict.fromkeys(SOURCE_PATH.findall(text[m.end():])))


def read_env(path: Path) -> dict:
    env = {}
    if path.is_file():
        for ln in path.read_text(encoding="utf-8").splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _openwiki_version() -> str:
    roots = [Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules"]   # Windows 기본
    try:
        roots.insert(0, Path(subprocess.run("npm root -g", shell=True, capture_output=True,
                                            text=True, check=True).stdout.strip()))
    except (OSError, subprocess.CalledProcessError):
        pass
    for root in roots:
        try:
            return json.loads((root / "openwiki" / "package.json")
                              .read_text(encoding="utf-8"))["version"]
        except (OSError, KeyError, json.JSONDecodeError):
            continue
    return "unknown"


def collect(name: str, force: bool) -> Path:
    src = WORK_DIR / "openwiki"
    pages_src = [p for p in src.rglob("*.md") if p.name != "INSTRUCTIONS.md"] if src.is_dir() else []
    if not pages_src:
        raise SystemExit(f"위키 페이지가 없습니다: {src} (openwiki --init 을 먼저 실행)")
    if (src / ".run.json").exists():
        print("경고: .run.json 이 남아 있습니다. 실행이 중단됐을 수 있습니다 (같은 명령으로 재개)")

    out = BASE / name
    if out.exists():
        if not force:
            raise SystemExit(f"이미 있습니다: {out} (덮어쓰려면 --force)")
        _rmtree(out)
    shutil.copytree(src, out, ignore=lambda d, names: [n for n in names if n in RUN_STATE])

    corpus = load_corpus()
    doc_ids = {d.doc_id for d in corpus.docs("doc")}
    pages, covered, invalid = [], set(), set()
    for p in sorted(out.rglob("*.md")):
        rel = p.relative_to(out).as_posix()
        if rel == "INSTRUCTIONS.md":
            continue
        text = p.read_text(encoding="utf-8")
        srcs = page_sources(text)
        covered.update(s for s in srcs if s in doc_ids)
        invalid.update(s for s in srcs if s not in doc_ids)
        pages.append({"page": rel, "tokens": count_tokens(text),
                      "sources": [s for s in srcs if s in doc_ids]})

    env = read_env(CONFIG_DIR / ".env")
    # index.md 는 OpenWiki 가 실행 후 자동 생성하는 목차라 Sources 가 없다
    content = [p for p in pages if not p["page"].endswith("index.md")]
    meta = {
        "variant": name,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "openwiki " + _openwiki_version(),
        "provider": env.get("OPENWIKI_PROVIDER", ""),
        "model": env.get("OPENWIKI_MODEL_ID", ""),
        "instructions_sha": git("hash-object", str(INSTRUCTIONS), cwd=CFG.root),
        "corpus_source": corpus.source,
        "corpus_manifest_sha256": manifest_sha256(corpus),
        "pages": len(pages),
        "tokens": sum(p["tokens"] for p in pages),
        "corpus_doc_tokens": sum(d.tokens for d in corpus.docs("doc")),
        "pages_without_sources": [p["page"] for p in content if not p["sources"]],
        "docs_covered": len(covered),
        "docs_total": len(doc_ids),
        "docs_uncovered": sorted(doc_ids - covered),
        "invalid_sources": sorted(invalid),
        "page_map": pages,
    }
    meta_path = BASE / f"{name}.meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")

    print(f"위키 {name}: 페이지 {meta['pages']}개, {meta['tokens']:,} 토큰 "
          f"(원본 문서 {meta['corpus_doc_tokens']:,} 토큰)")
    print(f"  원본 문서 커버리지 {meta['docs_covered']}/{meta['docs_total']}")
    if meta["pages_without_sources"]:
        print(f"  Sources 없는 페이지 {len(meta['pages_without_sources'])}개")
    if invalid:
        print(f"  코퍼스에 없는 Sources 경로 {len(invalid)}개")
    print(f"  -> {out}\n  -> {meta_path}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="이미 있는 결과를 지우고 다시 생성")
    ap.add_argument("--collect", action="store_true",
                    help="work/openwiki 를 고정 위키로 복사하고 메타·커버리지 기록")
    ap.add_argument("--name", default="wiki_v0", help="--collect 결과 이름")
    args = ap.parse_args()
    if args.collect:
        collect(args.name, args.force)
    else:
        build(args.force)


if __name__ == "__main__":
    main()
