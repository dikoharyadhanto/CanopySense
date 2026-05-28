"""
patcher_local.py — CanopySense Patcher-Local

Reads block geometries from local PostGIS, sends them to Patcher-Cloud as GeoJSON,
writes results back to satellite_data, and tracks batches in
patcher_run_log for cross-run retry intelligence.

Usage:
  python3 patcher_local.py                                             # scheduled: all blocks
  python3 patcher_local.py --estate-id 1                              # scheduled: estate scope
  python3 patcher_local.py --estate-id 1 --afdeling-id 2             # scheduled: afdeling scope
  python3 patcher_local.py --estate-id 1 --afdeling-id 2 --block-id 42  # upload: single block
  python3 patcher_local.py --backfill                                 # backfill: all, default 3yr
  python3 patcher_local.py --backfill --estate-id 1                   # backfill: estate scope
  python3 patcher_local.py --backfill --date-start 2024-01 --date-end 2024-03  # custom range

Env: CLOUD_FUNCTION_URL, PATCHER_API_KEY, CONTRACTOR_ID, PGDATABASE, PGUSER,
     PGPASSWORD, PGHOST, PGPORT, FUNCTION_TIMEOUT_SECONDS, BATCH_MODE,
     PATCHER_API_VERSION
"""
from __future__ import annotations
import argparse, calendar, hashlib, json, logging, os, pathlib, re, sys, time, uuid
from datetime import date, timedelta
from itertools import groupby
import psycopg2, psycopg2.extras, requests
from dotenv import load_dotenv
logger = logging.getLogger(__name__)
_BUILD_DIR  = pathlib.Path(__file__).parent
_ENV_FILE   = _BUILD_DIR.parent / "tests" / ".env"
_LOG_TABLE  = "patcher_run_log"
_TYPE_MAP   = {"block_id":int,"cloud_cover":float,"ndvi":float,"evi":float,"ndre":float,"savi":float,"gndvi":float}
_STALE_MIN  = 30
_BACKOFF    = [30, 60, 120]
_CB_THRESH  = 3
_CB_PAUSE   = 300
_DEFAULT_BACKFILL_YEARS = 3
_YM_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')

_BACKLOG_DDL = """
CREATE TABLE IF NOT EXISTS canopysense.backfill_skipped (
    id           SERIAL PRIMARY KEY,
    window_start DATE        NOT NULL,
    window_end   DATE        NOT NULL,
    batch_fp     TEXT        NOT NULL DEFAULT '',
    skip_reason  TEXT        NOT NULL,
    skipped_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (window_start, window_end, batch_fp)
);
"""

def _load_env() -> None:
    global _LOG_TABLE
    if _ENV_FILE.exists(): load_dotenv(_ENV_FILE, override=False)
    load_dotenv(override=False)
    _LOG_TABLE = f"{os.environ.get('PGSCHEMA','canopysense')}.patcher_run_log"

def _require(k: str) -> str:
    v = os.environ.get(k, "").strip()
    if not v: raise EnvironmentError(f"[ERROR] Missing required environment variable: {k}")
    return v

def _connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=os.environ.get("PGHOST","localhost"), port=int(os.environ.get("PGPORT",5432)),
        dbname=_require("PGDATABASE"), user=_require("PGUSER"),
        password=os.environ.get("PGPASSWORD",""),
    )

def _load_blocks(conn, estate_id: int | None = None,
                 afdeling_id: int | None = None, block_id: int | None = None) -> list[dict]:
    sql = ("SELECT b.id,b.code,b.name,b.afdeling_id,ST_AsGeoJSON(b.geometry) "
           "FROM canopysense.blocks b "
           "JOIN canopysense.afdelings a ON b.afdeling_id=a.id "
           "WHERE (%s IS NULL OR a.estate_id=%s) "
           "AND (%s IS NULL OR b.afdeling_id=%s) "
           "AND (%s IS NULL OR b.id=%s) "
           "ORDER BY a.estate_id,b.afdeling_id,b.id")
    params = (estate_id, estate_id, afdeling_id, afdeling_id, block_id, block_id)
    with conn.cursor() as cur:
        cur.execute(sql, params); rows = cur.fetchall()
    return [{"block_id":r[0],"code":r[1],"name":r[2],"afdeling_id":r[3],"geojson":r[4]} for r in rows]

def _group_batches(blocks: list[dict], mode: str) -> list[tuple]:
    if mode != "afdeling": return [(None, blocks)]
    key = lambda b: b["afdeling_id"]
    return [(k, list(g)) for k, g in groupby(sorted(blocks, key=key), key=key)]

def _fp(ids: list[int]) -> str:
    return hashlib.sha256(",".join(str(i) for i in sorted(ids)).encode()).hexdigest()

def _to_fc(blocks: list[dict]) -> dict:
    return {"type":"FeatureCollection","features":[
        {"type":"Feature","geometry":json.loads(b["geojson"]),
         "properties":{"block_id":b["block_id"],"code":b["code"],"name":b["name"]}}
        for b in blocks]}

def _log_write(conn, *, run_id, trigger_mode, afdeling_id, block_id,
               batch_fingerprint, status, rows_inserted=0, error_detail=None,
               api_version=None, started_at_now=False, estate_id=None,
               date_start=None, date_end=None) -> int:
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {_LOG_TABLE} (run_id,trigger_mode,afdeling_id,block_id,batch_fingerprint,"
            "status,rows_inserted,error_detail,api_version,started_at,estate_id,date_start,date_end) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,CASE WHEN %s THEN NOW() ELSE NULL END,%s,%s,%s) RETURNING id",
            (run_id,trigger_mode,afdeling_id,block_id,batch_fingerprint,
             status,rows_inserted,error_detail,api_version,started_at_now,
             estate_id,date_start,date_end))
        row_id = cur.fetchone()[0]
    conn.commit(); return row_id

def _log_update(conn, row_id: int, status: str, rows_inserted=0,
                error_detail=None, api_version=None) -> None:
    with conn.cursor() as cur:
        cur.execute(f"UPDATE {_LOG_TABLE} SET status=%s,rows_inserted=%s,"
                    "error_detail=%s,api_version=%s WHERE id=%s",
                    (status,rows_inserted,error_detail,api_version,row_id))
    conn.commit()

def _check_in_progress(conn, afdeling_id) -> str:
    """Return 'none', 'fresh', or 'stale'. Updates stale rows to FULL_FAILURE."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id, started_at <= NOW()-INTERVAL '{_STALE_MIN} minutes' "
            f"FROM {_LOG_TABLE} WHERE trigger_mode='scheduled' AND afdeling_id=%s "
            "AND status='IN_PROGRESS' ORDER BY started_at DESC LIMIT 1", (afdeling_id,))
        row = cur.fetchone()
    if not row: return "none"
    row_id, is_stale = row
    if is_stale:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE {_LOG_TABLE} SET status='FULL_FAILURE',"
                        "error_detail='{\"message\":\"Stale IN_PROGRESS — assumed crashed\"}' "
                        "WHERE id=%s", (row_id,))
        conn.commit(); return "stale"
    return "fresh"

def _get_retry_batches(conn) -> dict[int, dict]:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT DISTINCT ON (afdeling_id) afdeling_id,status,error_detail,batch_fingerprint "
            f"FROM {_LOG_TABLE} WHERE trigger_mode='scheduled' "
            "AND status IN ('FULL_FAILURE','PARTIAL_SUCCESS') "
            "ORDER BY afdeling_id,triggered_at DESC")
        return {r[0]:{"status":r[1],"error_detail":r[2],"batch_fingerprint":r[3]}
                for r in cur.fetchall()}

def _parse_row_generic(r: dict, cols: list[str]) -> tuple | None:
    try:
        def _cv(c, v):
            if c == "features": return psycopg2.extras.Json(json.loads(v) if isinstance(v,str) else (v or {}))
            return None if c in _TYPE_MAP and str(v).strip() in ("","None","null","NULL") else (_TYPE_MAP[c](v) if c in _TYPE_MAP else (str(v).strip() if v is not None else None))
        return tuple(_cv(c, r.get(c)) for c in cols)
    except (KeyError,ValueError) as e:
        logger.warning("Skipping malformed record: %s — %s", r, e); return None

def _execute_writes(conn, writes: list[dict], schema: str) -> int:
    total = 0
    for w in writes:
        cols, conflict = w["columns"], w["conflict_columns"]
        rows = [r2 for r in w.get("records",[]) if (r2:=_parse_row_generic(r,cols)) is not None]
        if not rows: continue
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur,f"INSERT INTO {schema}.{w['table']} ({','.join(cols)}) VALUES %s ON CONFLICT ({','.join(conflict)}) DO NOTHING",rows,page_size=500)
            conn.commit(); total += cur.rowcount if cur.rowcount >= 0 else len(rows)
    return total

def _presence_check_from_write(conn, write: dict, block_ids: list[int], schema: str,
                                date_start: str | None = None, date_end: str | None = None) -> int:
    if not (pc := write.get("presence_check")): logger.warning("No presence_check metadata in write entry — skipping"); return 0
    c, d = pc["block_id_column"], pc["recency_column"]
    with conn.cursor() as cur:
        if date_start and date_end:
            cur.execute(f"SELECT COUNT(DISTINCT {c}) FROM {schema}.{write['table']} WHERE {c}=ANY(%s) AND {d} BETWEEN %s AND %s",
                        (block_ids, date_start, date_end))
        else:
            days = pc.get("recency_days", 14)
            cur.execute(f"SELECT COUNT(DISTINCT {c}) FROM {schema}.{write['table']} WHERE {c}=ANY(%s) AND {d}>=CURRENT_DATE-INTERVAL '{days} days'",
                        (block_ids,))
        return cur.fetchone()[0]

def _call(url, api_key, contractor_id, fc, timeout,
          mode: str | None = None, date_start: str | None = None, date_end: str | None = None) -> dict:
    body: dict = {"api_version": "1.0", "blocks": fc}
    if mode:        body["mode"] = mode
    if date_start:  body["date_start"] = date_start
    if date_end:    body["date_end"]   = date_end
    resp = requests.post(url,
        headers={"X-API-Key":api_key,"Content-Type":"application/json","X-Contractor-Id":contractor_id},
        json=body, timeout=timeout)
    resp.raise_for_status(); return resp.json()

def _call_with_retry(url, api_key, contractor_id, fc, timeout, cb: list[int],
                     mode: str | None = None, date_start: str | None = None,
                     date_end: str | None = None) -> tuple[dict|None,str]:
    """Exponential backoff (30→60→120s). Mutates cb[0] for circuit breaker. Raises SystemExit on 401/403."""
    last_err = ""
    for attempt, wait_s in enumerate((*_BACKOFF, None), start=1):
        try:
            data = _call(url, api_key, contractor_id, fc, timeout, mode, date_start, date_end)
        except requests.exceptions.HTTPError as exc:
            code = exc.response.status_code
            if code in (401,403):
                logger.error("[ERROR] %s — Stopping run.", exc.response.text.strip()); raise SystemExit(1)
            if code == 429:
                cb[0] += 1
                if cb[0] >= _CB_THRESH:
                    logger.warning("[WARN] Circuit breaker triggered — 3 consecutive 429s. Pausing run for 5 minutes.")
                    time.sleep(_CB_PAUSE); cb[0] = 0
            last_err = f"HTTP {code}"
        except requests.exceptions.RequestException as exc:
            last_err = str(exc)[:200]
        else:
            missing = next((f for f in ("api_version","writes","rows_returned","errors") if f not in data), None)
            if missing:
                last_err = f"Response missing required field: {missing}"
                logger.warning("[WARN] %s. Retrying...", last_err)
            else:
                cb[0] = 0
                ver = data.get("api_version",""); expected = os.environ.get("PATCHER_API_VERSION","1.0")
                if ver and ver != expected:
                    logger.warning("[WARN] Patcher-Cloud api_version=%s detected. Consider updating patcher_local.py.", ver)
                return data, ""
        if wait_s is not None:
            logger.warning("[WARN] Attempt %d failed (%s). Retrying in %ds...", attempt, last_err, wait_s)
            time.sleep(wait_s)
    return None, last_err

def _run_batch(conn, run_id, trigger_mode, afdeling_id, block_id, blocks, url, api_key,
               contractor_id, timeout, cb, num, total, schema,
               estate_id=None, date_start=None, date_end=None) -> str:
    ids = [b["block_id"] for b in blocks]
    fp = _fp(ids)
    label = f"Batch {num}/{total} (afdeling_id={afdeling_id}, {len(blocks)} blocks, fingerprint={fp[:8]})"
    logger.info("[INFO]  %s — sending to Cloud Function", label)
    log_id = _log_write(conn, run_id=run_id, trigger_mode=trigger_mode, afdeling_id=afdeling_id,
                        block_id=block_id, batch_fingerprint=fp, status="IN_PROGRESS", started_at_now=True,
                        estate_id=estate_id, date_start=date_start, date_end=date_end)
    data, err = _call_with_retry(url, api_key, contractor_id, _to_fc(blocks), timeout, cb,
                                 mode=trigger_mode, date_start=date_start, date_end=date_end)
    writes = (data or {}).get("writes", [])
    rows_i = _execute_writes(conn, writes, schema) if data else 0
    first_w = writes[0] if writes else {}
    present = _presence_check_from_write(conn, first_w, ids, schema, date_start=date_start, date_end=date_end) if first_w else 0
    api_ver = (data or {}).get("api_version")
    errors_returned = (data or {}).get("errors", [])
    if data is None:
        status, ed = "FULL_FAILURE", json.dumps({"message": err})
        logger.error("[ERROR] %s — FULL_FAILURE after 3 attempts. Recorded for next run.", label)
    elif rows_i == 0 and len(errors_returned) == len(ids):
        # Cloud Function ran but no scene/data for this window — distinct from network failure
        status, ed = "NO_NEW_DATA", json.dumps({"message": "No satellite data for this window"})
        logger.info("[INFO]  %s — NO_NEW_DATA | window %s→%s returned 0 rows | api_version=%s",
                    label, date_start, date_end, api_ver)
    elif present == len(ids):
        status, ed = "FULL_SUCCESS", None
        logger.info("[INFO]  %s — FULL_SUCCESS | rows_inserted=%d | presence_check=%d/%d | api_version=%s",
                    label, rows_i, present, len(ids), api_ver)
    elif present > 0:
        out_ids = {int(r["block_id"]) for w in data.get("writes",[]) for r in w.get("records",[])}
        missing = [i for i in ids if i not in out_ids]
        status, ed = "PARTIAL_SUCCESS", json.dumps({"missing_block_ids": missing})
        logger.warning("[WARN]  %s — PARTIAL_SUCCESS | presence_check=%d/%d | missing_block_ids=%s",
                       label, present, len(ids), missing)
    else:
        status, ed = "FULL_FAILURE", json.dumps({"message":"Zero blocks present after run"})
        logger.error("[ERROR] %s — FULL_FAILURE | presence_check=0/%d", label, len(ids))
    _log_update(conn, log_id, status, rows_i, ed, api_ver)
    return status

def _run_scheduled(conn, run_id, url, api_key, contractor_id, timeout, schema,
                   estate_id: int | None = None, afdeling_id: int | None = None) -> int:
    mode = os.environ.get("BATCH_MODE","afdeling")
    all_blocks = _load_blocks(conn, estate_id=estate_id, afdeling_id=afdeling_id)
    if not all_blocks:
        logger.warning("[WARN]  No blocks found. Nothing to do."); return 0
    batches = _group_batches(all_blocks, mode)
    scope_label = (f"estate_id={estate_id}" if estate_id and not afdeling_id
                   else f"estate_id={estate_id}/afdeling_id={afdeling_id}" if afdeling_id
                   else "all estates")
    logger.info("[INFO]  Run started — mode: scheduled | scope: %s | run_id: %s", scope_label, run_id[:8])
    logger.info("[INFO]  Blocks loaded: %d across %d batches", len(all_blocks), len(batches))
    retry_map = _get_retry_batches(conn)
    if retry_map: logger.info("[INFO]  Retrying %d previously failed batch(es) first", len(retry_map))
    cb = [0]
    counts = {"FULL_SUCCESS":0,"PARTIAL_SUCCESS":0,"FULL_FAILURE":0,"SKIPPED":0}
    retry_b = [(aid,retry_map[aid],blks) for aid,blks in batches if aid in retry_map]
    new_b   = [(aid,None,blks) for aid,blks in batches if aid not in retry_map]
    ordered = retry_b + new_b
    for i, (aid, rinfo, blks) in enumerate(ordered, 1):
        if not blks:
            logger.info("[INFO]  Batch %d/%d (afdeling_id=%s) — SKIPPED (empty)", i, len(ordered), aid)
            _log_write(conn,run_id=run_id,trigger_mode="scheduled",afdeling_id=aid,block_id=None,
                       batch_fingerprint=None,status="SKIPPED",estate_id=estate_id); counts["SKIPPED"]+=1; continue
        guard = _check_in_progress(conn, aid)
        if guard == "fresh":
            logger.warning("[WARN]  Concurrent run detected for afdeling_id=%s. Skipping.", aid)
            counts["SKIPPED"]+=1; continue
        if guard == "stale":
            logger.info("[INFO]  Stale IN_PROGRESS found for afdeling_id=%s (%d min). "
                        "Marking FULL_FAILURE and retrying.", aid, _STALE_MIN)
        if rinfo and rinfo["status"]=="PARTIAL_SUCCESS" and rinfo.get("error_detail"):
            try:
                miss = set(json.loads(rinfo["error_detail"]).get("missing_block_ids",[]))
                if miss: blks = [b for b in blks if b["block_id"] in miss]
            except (json.JSONDecodeError,KeyError): pass
        if rinfo and rinfo.get("batch_fingerprint") and _fp([b["block_id"] for b in blks]) != rinfo["batch_fingerprint"]:
            logger.info("[INFO]  Batch fingerprint changed for afdeling_id=%s. Treating as new batch.", aid)
        st = _run_batch(conn,run_id,"scheduled",aid,None,blks,url,api_key,contractor_id,timeout,cb,i,len(ordered),
                        schema,estate_id=estate_id)
        counts[st] = counts.get(st,0)+1
    logger.info("[INFO]  Run complete — %d/%d FULL_SUCCESS | %d PARTIAL_SUCCESS | %d FULL_FAILURE | %d SKIPPED",
                counts["FULL_SUCCESS"],len(ordered),counts["PARTIAL_SUCCESS"],counts["FULL_FAILURE"],counts["SKIPPED"])
    return 1 if counts["FULL_FAILURE"] > 0 else 0

def _run_upload(conn, run_id, estate_id, afdeling_id, block_id,
                url, api_key, contractor_id, timeout, schema) -> int:
    logger.info("[INFO]  Run started — mode: upload | estate_id=%s afdeling_id=%s block_id=%d | run_id: %s",
                estate_id, afdeling_id, block_id, run_id[:8])
    blks = _load_blocks(conn, estate_id=estate_id, afdeling_id=afdeling_id, block_id=block_id)
    if not blks:
        logger.info("[INFO]  [SKIPPED] block_id=%d not found in scope", block_id)
        _log_write(conn,run_id=run_id,trigger_mode="upload",afdeling_id=afdeling_id,
                   block_id=block_id,batch_fingerprint=None,status="SKIPPED",
                   estate_id=estate_id); return 0
    st = _run_batch(conn,run_id,"upload",blks[0]["afdeling_id"],blks[0]["block_id"],blks,
                    url,api_key,contractor_id,timeout,[0],1,1,schema,estate_id=estate_id)
    return 0 if st in ("FULL_SUCCESS","PARTIAL_SUCCESS") else 1

def _ensure_backlog_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_BACKLOG_DDL)
    conn.commit()


def _has_existing_data(conn, date_start: str, date_end: str,
                        block_ids: list[int] | None = None) -> bool:
    with conn.cursor() as cur:
        if block_ids:
            cur.execute(
                "SELECT 1 FROM canopysense.satellite_data "
                "WHERE block_id=ANY(%s) AND acquisition_date BETWEEN %s AND %s LIMIT 1",
                (block_ids, date_start, date_end))
        else:
            cur.execute(
                "SELECT 1 FROM canopysense.satellite_data "
                "WHERE acquisition_date BETWEEN %s AND %s LIMIT 1",
                (date_start, date_end))
        return cur.fetchone() is not None


def _is_in_backlog(conn, date_start: str, date_end: str, batch_fp: str = "") -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM canopysense.backfill_skipped "
            "WHERE window_start=%s AND window_end=%s AND batch_fp=%s LIMIT 1",
            (date_start, date_end, batch_fp))
        return cur.fetchone() is not None


def _write_to_backlog(conn, date_start: str, date_end: str, batch_fp: str, reason: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO canopysense.backfill_skipped (window_start,window_end,batch_fp,skip_reason) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT (window_start,window_end,batch_fp) DO NOTHING",
            (date_start, date_end, batch_fp, reason))
    conn.commit()


def _generate_weekly_chunks(start_ym: str, end_ym: str) -> list[tuple[str, str, str]]:
    start_year, start_month = int(start_ym[:4]), int(start_ym[5:7])
    end_year,   end_month   = int(end_ym[:4]),   int(end_ym[5:7])
    _, last_day = calendar.monthrange(end_year, end_month)
    period_start = date(start_year, start_month, 1)
    period_end   = date(end_year, end_month, last_day)
    chunks: list[tuple[str, str, str]] = []
    current = period_start
    while current <= period_end:
        chunk_end = min(current + timedelta(days=6), period_end)
        label = f"{current.strftime('%d %b %Y')} → {chunk_end.strftime('%d %b %Y')}"
        chunks.append((current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d"), label))
        current = chunk_end + timedelta(days=1)
    return chunks


def _run_backfill(conn, run_id, url, api_key, contractor_id, timeout, schema,
                  estate_id, afdeling_id, block_id, date_start_ym, date_end_ym) -> int:
    chunks = _generate_weekly_chunks(date_start_ym, date_end_ym)
    scope_label = (f"estate_id={estate_id}" if estate_id and not afdeling_id
                   else f"estate_id={estate_id}/afdeling_id={afdeling_id}" if afdeling_id
                   else "all estates")
    logger.info("[INFO]  Backfill started | %d chunks | %s → %s | scope: %s | run_id: %s",
                len(chunks), date_start_ym, date_end_ym, scope_label, run_id[:8])
    _ensure_backlog_table(conn)
    blocks = _load_blocks(conn, estate_id=estate_id, afdeling_id=afdeling_id, block_id=block_id)
    if not blocks:
        logger.warning("[WARN]  No blocks found in scope. Nothing to backfill."); return 0
    cb = [0]
    counts = {"FULL_SUCCESS":0,"PARTIAL_SUCCESS":0,"FULL_FAILURE":0,"NO_NEW_DATA":0,"SKIPPED":0}
    batch_mode = os.environ.get("BATCH_MODE","afdeling")
    for idx, (chunk_start, chunk_end, label) in enumerate(chunks, 1):
        logger.info("[INFO]  Backfill chunk %d/%d: %s", idx, len(chunks), label)
        # Group blocks by afdeling; L1/L2 checks are per-batch to avoid cross-scope skips
        batches = _group_batches(blocks, batch_mode)
        for b_idx, (aid, blks) in enumerate(batches, 1):
            if not blks: continue
            batch_ids = [b["block_id"] for b in blks]
            batch_fp  = _fp(batch_ids)
            if _has_existing_data(conn, chunk_start, chunk_end, batch_ids):
                logger.info("[INFO]  [SKIP-L1] Already in satellite_data: %s afdeling_id=%s", label, aid)
                counts["SKIPPED"] += 1; continue
            if _is_in_backlog(conn, chunk_start, chunk_end, batch_fp):
                logger.info("[INFO]  [SKIP-L2] In backfill_skipped: %s afdeling_id=%s", label, aid)
                counts["SKIPPED"] += 1; continue
            st = _run_batch(conn, run_id, "backfill", aid, block_id, blks,
                            url, api_key, contractor_id, timeout, cb,
                            b_idx, len(batches), schema,
                            estate_id=estate_id,
                            date_start=chunk_start, date_end=chunk_end)
            counts[st] = counts.get(st, 0) + 1
            if st == "NO_NEW_DATA":
                _write_to_backlog(conn, chunk_start, chunk_end, batch_fp, "no_new_data_cloud_route")
    logger.info("[INFO]  Backfill complete — %d FULL_SUCCESS | %d PARTIAL_SUCCESS | "
                "%d FULL_FAILURE | %d NO_NEW_DATA | %d SKIPPED",
                counts["FULL_SUCCESS"], counts["PARTIAL_SUCCESS"],
                counts["FULL_FAILURE"], counts["NO_NEW_DATA"], counts["SKIPPED"])
    return 1 if counts["FULL_FAILURE"] > 0 else 0


def main() -> int:
    today = date.today()
    default_end_ym   = today.strftime("%Y-%m")
    default_start_ym = today.replace(year=today.year - _DEFAULT_BACKFILL_YEARS).strftime("%Y-%m")

    parser = argparse.ArgumentParser(description="CanopySense Patcher-Local v1.3")
    parser.add_argument("--estate-id",   type=int, default=None,
                        help="Scope to a specific estate. Required if --afdeling-id or --block-id given.")
    parser.add_argument("--afdeling-id", type=int, default=None,
                        help="Scope to a specific afdeling. Requires --estate-id.")
    parser.add_argument("--block-id",    type=int, default=None,
                        help="Upload mode: single block. Requires --estate-id and --afdeling-id.")
    parser.add_argument("--backfill",    action="store_true", default=False,
                        help="Run historical backfill mode.")
    parser.add_argument("--date-start",  default=None,
                        help=f"Backfill start month YYYY-MM (default: {default_start_ym})")
    parser.add_argument("--date-end",    default=None,
                        help=f"Backfill end month YYYY-MM (default: {default_end_ym})")
    parser.add_argument("--run-id",      default=None,
                        help="Pre-assigned run UUID (used when triggered from admin UI).")
    args = parser.parse_args()

    # Hierarchy validation
    if args.block_id is not None and (args.afdeling_id is None or args.estate_id is None):
        logger.error("[ERROR] --block-id requires both --afdeling-id and --estate-id"); return 1
    if args.afdeling_id is not None and args.estate_id is None:
        logger.error("[ERROR] --afdeling-id requires --estate-id"); return 1

    # Date validation (backfill mode) — explicit fail before DB/cloud operations
    if args.backfill:
        for flag, val in (("--date-start", args.date_start), ("--date-end", args.date_end)):
            if val and not _YM_RE.match(val):
                logger.error("[ERROR] %s must be YYYY-MM format (e.g. 2024-01), got: %s", flag, val); return 1
        eff_start = args.date_start or default_start_ym
        eff_end   = args.date_end   or default_end_ym
        if eff_start > eff_end:
            logger.error("[ERROR] --date-start (%s) must not be after --date-end (%s)", eff_start, eff_end); return 1

    _load_env()
    try:
        url=_require("CLOUD_FUNCTION_URL"); api_key=_require("PATCHER_API_KEY"); contractor_id=_require("CONTRACTOR_ID")
    except EnvironmentError as exc:
        logger.error("%s", exc); return 1
    timeout = int(os.environ.get("FUNCTION_TIMEOUT_SECONDS",120))
    schema  = os.environ.get("PGSCHEMA","canopysense")
    run_id  = args.run_id if args.run_id else str(uuid.uuid4())
    try:
        conn = _connect()
    except Exception as exc:
        logger.error("[ERROR] PostGIS connection failed: %s", exc); return 1
    try:
        if args.backfill:
            start_ym = args.date_start or default_start_ym
            end_ym   = args.date_end   or default_end_ym
            return _run_backfill(conn, run_id, url, api_key, contractor_id, timeout, schema,
                                 args.estate_id, args.afdeling_id, args.block_id, start_ym, end_ym)
        if args.block_id is not None:
            return _run_upload(conn, run_id, args.estate_id, args.afdeling_id, args.block_id,
                               url, api_key, contractor_id, timeout, schema)
        return _run_scheduled(conn, run_id, url, api_key, contractor_id, timeout, schema,
                              estate_id=args.estate_id, afdeling_id=args.afdeling_id)
    except SystemExit as exc:
        return int(exc.code)
    except Exception as exc:
        logger.error("[ERROR] Unexpected error: %s", exc, exc_info=True); return 1
    finally:
        conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    sys.exit(main())
