"""
hr/video_index_manager.py
Parse đúng tên file RecordWorker: {order_code}_C{cam_id}_{emp_id}_{YYYYMMDD}_{HHMMSS}.mp4
Keys output khớp với hr_page.py: camera_id, camera_name, date, start_time,
duration_sec, order_code, employee_name, department, file_size_mb, file_path
"""

import glob
import json
import os
import re
from datetime import datetime, timedelta

from hr.report_db import insert_video_report

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_STORAGE = os.path.join(_ROOT, "recordings")
INDEX_DIR = "index"

# ─── helpers ────────────────────────────────────────────────────────────────

def _storage_path() -> str:
    try:
        from core.config_manager import load_config
        return load_config().get("storage_path") or _DEFAULT_STORAGE
    except Exception:
        return _DEFAULT_STORAGE


def _cameras_map() -> dict:
    """{ str(cam_id): camera_dict }  từ config.json"""
    try:
        from core.config_manager import load_config
        return {str(c["id"]): c for c in load_config().get("cameras", [])}
    except Exception:
        return {}


def _employees_map() -> dict:
    """{ emp_id: employee_dict }  từ employees.json"""
    try:
        from hr.employee_manager import load_employees
        return {str(e["id"]): e for e in load_employees()}
    except Exception:
        return {}


def _parse_filename(fname: str, cam_map: dict, emp_map: dict) -> dict:
    """
    Tên file theo RecordWorker._build_output_name:
        {order_code}_C{cam_id}_{emp_id}_{YYYYMMDD}_{HHMMSS}.mp4

    Ví dụ thực tế từ screenshot:
        SPXVN062941946373_C11_000001_20260503_223806.mp4
        order_code = SPXVN062941946373
        cam_id     = 11
        emp_id     = 000001
        date       = 2026-05-03
        time       = 22:38:06
    """
    stem = re.sub(r'\.(mp4|avi|mkv|mov)$', '', fname, flags=re.IGNORECASE)

    order_code  = "NOORDER"
    cam_id_raw  = "?"
    emp_id      = "NOEMP"
    date_str    = ""
    time_str    = "00:00:00"
    dt_iso      = ""

    try:
        # Tìm pattern _C{digits hoặc chữ}_ để tách order / cam / phần còn lại
        m = re.search(r'_C([^_]+)_', stem)
        if m:
            cam_id_raw = m.group(1)
            order_code = stem[:m.start()].strip("_") or "NOORDER"
            rest       = stem[m.end():]          # emp_id_YYYYMMDD_HHMMSS
            parts      = rest.split("_")

            if len(parts) >= 3:
                emp_id  = parts[0]
                raw_d   = parts[1]   # YYYYMMDD
                raw_t   = parts[2]   # HHMMSS

                if len(raw_d) == 8 and raw_d.isdigit():
                    date_str = f"{raw_d[:4]}-{raw_d[4:6]}-{raw_d[6:8]}"
                if len(raw_t) >= 6 and raw_t[:6].isdigit():
                    time_str = f"{raw_t[:2]}:{raw_t[2:4]}:{raw_t[4:6]}"

                if date_str:
                    dt_iso = f"{date_str}T{time_str}"
    except Exception:
        pass

    cam_info = cam_map.get(cam_id_raw, {})
    emp_info = emp_map.get(emp_id, {})

    return {
        "camera_id":     cam_id_raw,
        "camera_name":   cam_info.get("name", f"Camera {cam_id_raw}"),
        "order_code":    order_code,
        "emp_id":        emp_id,
        "employee_name": emp_info.get("name", ""),
        "department":    emp_info.get("department", ""),
        "position":      emp_info.get("position", ""),
        "date":          date_str,
        "dt_iso":        dt_iso,
    }


def _get_duration_sec(fpath: str, size_mb: float) -> int:
    """Đọc duration thực bằng cv2 nếu có, fallback ước tính ~1 MB/s."""
    try:
        import cv2
        cap   = cv2.VideoCapture(fpath)
        fps   = cap.get(cv2.CAP_PROP_FPS)   or 20
        total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        cap.release()
        if fps > 0 and total > 0:
            return max(1, int(total / fps))
    except Exception:
        pass
    return max(1, int(size_mb))


# ─── core scan ──────────────────────────────────────────────────────────────

def build_index(storage_path: str = None) -> dict:
    base = storage_path or _storage_path()
    os.makedirs(base, exist_ok=True)

    index_dir = os.path.join(base, INDEX_DIR)
    os.makedirs(index_dir, exist_ok=True)

    cam_map = _cameras_map()
    emp_map = _employees_map()

    videos_by_date = {}
    all_videos = []

    for ext in ("*.mp4", "*.avi", "*.mkv", "*.mov", "*.ts"):
        for fpath in sorted(glob.glob(os.path.join(base, "**", ext), recursive=True)):

            # bỏ qua thư mục index
            if os.path.normpath(index_dir) in os.path.normpath(fpath):
                continue

            fname = os.path.basename(fpath)
            stat = os.stat(fpath)

            size_bytes = stat.st_size
            size_mb = round(size_bytes / (1024 * 1024), 2)
            mtime = datetime.fromtimestamp(stat.st_mtime)

            p = _parse_filename(fname, cam_map, emp_map)
            duration = _get_duration_sec(fpath, size_mb)

            if not p["date"]:
                p["date"] = mtime.strftime("%Y-%m-%d")
                p["dt_iso"] = mtime.strftime("%Y-%m-%dT%H:%M:%S")

            start_iso = p["dt_iso"]

            try:
                end_iso = (
                    datetime.fromisoformat(start_iso)
                    + timedelta(seconds=duration)
                ).isoformat()
            except Exception:
                end_iso = start_iso

            rel_path = os.path.relpath(fpath, base).replace("\\", "/")

            vid_id = (
                f"VID_C{p['camera_id']}_"
                f"{p['date'].replace('-', '')}_"
                f"{start_iso[11:].replace(':', '')}"
            )

            entry = {
                "id": vid_id,
                "filename": fname,
                "file_path": rel_path,
                "file_size_mb": size_mb,
                "file_size_bytes": size_bytes,

                "camera_id": p["camera_id"],
                "camera_name": p["camera_name"],

                "date": p["date"],
                "start_time": start_iso,
                "end_time": end_iso,
                "duration_sec": duration,

                "order_code": p["order_code"],
                "qr_code": p["order_code"],

                "employee_id": p["emp_id"],
                "employee_name": p["employee_name"],
                "department": p["department"],
                "position": p["position"],

                "trigger_type": "qr",
                "status": "completed",
                "created_at": mtime.isoformat(),
            }

            date_key = entry["date"]
            videos_by_date.setdefault(date_key, []).append(entry)
            all_videos.append(entry)

            insert_video_report(entry)

    # xoá index ngày cũ để build lại sạch
    for old_file in glob.glob(os.path.join(index_dir, "*.json")):
        try:
            os.remove(old_file)
        except Exception:
            pass

    # ghi index theo từng ngày
    for date_key, items in videos_by_date.items():
        day_file = os.path.join(index_dir, f"{date_key}.json")

        payload = {
            "schema_version": "2.2",
            "date": date_key,
            "generated_at": datetime.now().isoformat(),
            "storage_path": base,
            "total": len(items),
            "videos": items,
        }

        with open(day_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    return {
        "schema_version": "2.2",
        "generated_at": datetime.now().isoformat(),
        "storage_path": base,
        "total": len(all_videos),
        "videos": all_videos,
    }


# Alias – các chỗ khác gọi tên này
scan_and_build_index = build_index
scan_recordings = lambda d=None: build_index(d).get("videos", [])


# ─── load ────────────────────────────────────────────────────────────────────

def load_index(storage_path: str = None) -> dict:
    base = storage_path or _storage_path()
    index_dir = os.path.join(base, INDEX_DIR)

    if not os.path.exists(index_dir):
        return build_index(base)

    videos = []

    for fp in sorted(glob.glob(os.path.join(index_dir, "*.json")), reverse=True):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)

            videos.extend(data.get("videos", []))

        except Exception as e:
            print("[INDEX LOAD ERROR]", fp, e)

    return {
        "schema_version": "2.2",
        "generated_at": datetime.now().isoformat(),
        "storage_path": base,
        "total": len(videos),
        "videos": videos,
    }


def append_video_entry(entry: dict, storage_path: str = None):
    base = storage_path or _storage_path()

    index_dir = os.path.join(base, INDEX_DIR)
    os.makedirs(index_dir, exist_ok=True)

    date_key = entry.get("date") or str(entry.get("start_time", ""))[:10]

    if not date_key:
        date_key = datetime.now().strftime("%Y-%m-%d")

    day_file = os.path.join(index_dir, f"{date_key}.json")

    data = {
        "schema_version": "2.2",
        "date": date_key,
        "generated_at": datetime.now().isoformat(),
        "storage_path": base,
        "total": 0,
        "videos": [],
    }

    if os.path.exists(day_file):
        try:
            with open(day_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    seen = {v.get("filename") for v in data.get("videos", [])}

    if entry.get("filename") not in seen:
        data["videos"].append(entry)
        insert_video_report(entry)

    data["total"] = len(data["videos"])
    data["generated_at"] = datetime.now().isoformat()

    with open(day_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def build_video_info(storage_path, full_path):
    base = storage_path or _storage_path()

    cam_map = _cameras_map()
    emp_map = _employees_map()

    fname = os.path.basename(full_path)
    stat = os.stat(full_path)

    size_bytes = stat.st_size
    size_mb = round(size_bytes / (1024 * 1024), 2)
    mtime = datetime.fromtimestamp(stat.st_mtime)

    p = _parse_filename(fname, cam_map, emp_map)

    duration = _get_duration_sec(full_path, size_mb)

    if not p["date"]:
        p["date"] = mtime.strftime("%Y-%m-%d")
        p["dt_iso"] = mtime.strftime("%Y-%m-%dT%H:%M:%S")

    start_iso = p["dt_iso"]

    try:
        end_iso = (
            datetime.fromisoformat(start_iso)
            + timedelta(seconds=duration)
        ).isoformat()
    except Exception:
        end_iso = start_iso

    rel_path = os.path.relpath(full_path, base).replace("\\", "/")

    vid_id = (
        f"VID_C{p['camera_id']}_"
        f"{p['date'].replace('-', '')}_"
        f"{start_iso[11:].replace(':', '')}"
    )

    return {
        "id": vid_id,
        "filename": fname,
        "file_path": rel_path,
        "file_size_mb": size_mb,
        "file_size_bytes": size_bytes,

        "camera_id": p["camera_id"],
        "camera_name": p["camera_name"],

        "date": p["date"],
        "start_time": start_iso,
        "end_time": end_iso,
        "duration_sec": duration,

        "order_code": p["order_code"],
        "qr_code": p["order_code"],

        "employee_id": p["emp_id"],
        "employee_name": p["employee_name"],
        "department": p["department"],
        "position": p["position"],

        "trigger_type": "qr",
        "status": "completed",
        "created_at": mtime.isoformat(),
    }


def save_index_by_day(storage_path, videos):
    base = storage_path or _storage_path()

    index_dir = os.path.join(base, INDEX_DIR)
    os.makedirs(index_dir, exist_ok=True)

    videos_by_date = {}

    for v in videos:
        date_key = v.get("date") or str(v.get("start_time", ""))[:10]

        if not date_key:
            date_key = datetime.now().strftime("%Y-%m-%d")

        videos_by_date.setdefault(date_key, []).append(v)

    for date_key, items in videos_by_date.items():
        day_file = os.path.join(index_dir, f"{date_key}.json")

        payload = {
            "schema_version": "2.2",
            "date": date_key,
            "generated_at": datetime.now().isoformat(),
            "storage_path": base,
            "total": len(items),
            "videos": items,
        }

        with open(day_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

#─── incremental update ─────────────────────────────────────────────────────
def update_index_incremental(storage_path):
    old_index = load_index(storage_path)
    old_videos = old_index.get("videos", [])

    existed = set(
        str(v.get("file_path") or v.get("path") or "").replace("\\", "/")
        for v in old_videos
    )

    new_videos = []

    for root, dirs, files in os.walk(storage_path):
        if os.path.basename(root).lower() == "index":
            continue

        for name in files:
            if not name.lower().endswith((".mp4", ".mkv", ".avi", ".mov", ".ts")):
                continue

            full_path = os.path.join(root, name)
            rel_path = os.path.relpath(full_path, storage_path).replace("\\", "/")

            if rel_path in existed:
                continue

            video = build_video_info(storage_path, full_path)
            new_videos.append(video)
            insert_video_report(video)

    all_videos = old_videos + new_videos

    save_index_by_day(storage_path, all_videos)
    generate_html_report(storage_path)

    return {
        "total": len(all_videos),
        "new": len(new_videos),
        "videos": all_videos,
    }

def _iso_to_vn_date(date_text: str) -> str:
    """
    yyyy-mm-dd -> dd/mm/yyyy
    """
    date_text = str(date_text or "").strip()

    try:
        y, m, d = date_text.split("-")
        if len(y) == 4:
            return f"{d}/{m}/{y}"
    except Exception:
        pass

    return date_text

# ─── HTML report ─────────────────────────────────────────────────────────────

def generate_html_report(storage_path: str = None) -> str:
    """
    Sinh index.html tra cứu + phát video.
    - Nút Phát dùng đường dẫn tuyệt đối (file://) để trình duyệt mở được
    - Lọc được theo Camera / Ngày / Mã đơn / Nhân viên
    """
    base  = storage_path or _storage_path()
    index = load_index(base)
    vids  = index.get("videos", [])

    # ── Options cho filter camera ──
    cam_opts = "".join(
        f'<option value="{cid}">{cname}</option>'
        for cid, cname in sorted(
            {(v["camera_id"], v["camera_name"]) for v in vids},
            key=lambda x: x[0]
        )
    )

    total_size = sum(v.get("file_size_mb", 0) for v in vids)

    # ── Build rows ──
    rows = ""
    for v in vids:
        dur     = v.get("duration_sec", 0)
        dur_txt = f"{dur // 60}:{dur % 60:02d}"
        emp     = v.get("employee_name") or v.get("employee_id") or "—"
        dept    = v.get("department") or "—"
        order   = v.get("order_code") or "—"
        date = v.get("date", "")
        date_show = _iso_to_vn_date(date)

        time = v.get("start_time", "")[11:16]
        cam_id  = v.get("camera_id", "")
        cam_nm  = v.get("camera_name", cam_id)
        sz      = v.get("file_size_mb", 0)
        fname   = v.get("filename", "").replace("'", "\\'")

        # Đường dẫn tuyệt đối cho trình duyệt phát được
        abs_path = os.path.join(base, v.get("file_path", v.get("filename", "")))
        abs_path = abs_path.replace("\\", "/")
        
        # Encode thành file:// URL
        rel_url = v.get("file_path", v.get("filename", "")).replace("\\", "/")
        play_url = rel_url

        fname_dl = v.get('filename', '')

        rows += (
            f'<tr data-cam="{cam_id}" data-date="{date}" '
            f'data-order="{order.lower()}" data-emp="{emp.lower()}">\n'
            
            f'  <td><span class="badge">{cam_id}</span></td>\n'
            f'  <td class="order-col">{order}</td>\n'
            f'  <td>{emp}</td>\n'
            f'  <td>{dept}</td>\n'
            f'  <td>{date_show}</td>\n'
            f'  <td>{time}</td>\n'
            f'  <td>{dur_txt}</td>\n'
            f'  <td>{sz} MB</td>\n'


            f'  <td>\n'
            f'    <button class="bp" onclick="pv(\'{play_url}\',\'{fname}\')">&#9654; Ph&#225;t</button>\n'
            f'    <a class="bd" href="{play_url}" download="{fname_dl}">&#11015; T&#7843;i</a>\n'
            f'  </td>\n'
            f'</tr>\n'
        )

    empty_row = ('<tr><td colspan="9" style="text-align:center;padding:48px;color:#64748b">'
                 'Ch&#432;a c&#243; video n&#224;o trong th&#432; m&#7909;c n&#224;y.</td></tr>')

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CCTV AI \u2013 Tra c\u1ee9u Video</title>
<style>
:root{{
  --bg:#0b0f19; --panel:#111827; --bd:#1f2937;
  --ac:#3b82f6; --ac2:#93c5fd; --tx:#f1f5f9; --mu:#64748b;
  --gn:#22c55e; --rd:#ef4444; --or:#f59e0b; --yw:#eab308;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font-family:system-ui,'Segoe UI',sans-serif;font-size:13px;min-height:100vh}}
header{{background:var(--panel);border-bottom:1px solid var(--bd);padding:14px 24px;display:flex;align-items:center;gap:12px}}
.logo{{font-size:22px}}
header h1{{font-size:15px;font-weight:700;letter-spacing:.02em}}
header .sub{{color:var(--mu);font-family:monospace;font-size:11px;margin-top:3px}}
.stats{{display:flex;gap:12px;padding:16px 24px;flex-wrap:wrap}}
.sc{{background:var(--panel);border:1px solid var(--bd);border-radius:8px;padding:12px 20px;min-width:130px}}
.sc .v{{font-size:24px;font-weight:700;font-family:monospace}}
.sc .l{{font-size:11px;color:var(--mu);margin-top:2px}}
.filters{{padding:0 24px 14px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
.fi{{background:var(--panel);border:1px solid var(--bd);color:var(--tx);
     padding:7px 11px;border-radius:6px;font-size:12px;font-family:inherit;outline:none}}
.fi:focus{{border-color:var(--ac)}}
.fi-kw{{width:230px}} .fi-cam{{min-width:160px}} .fi-date{{width:145px}} .fi-order{{width:130px}}
.rb{{background:var(--ac);color:#fff;border:none;padding:7px 16px;border-radius:6px;
     cursor:pointer;font-weight:700;font-size:12px;font-family:inherit}}
.rb:hover{{background:#2563eb}}
.tw{{padding:0 24px 48px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;min-width:900px}}
thead tr{{background:var(--panel);border-bottom:2px solid var(--bd)}}
th{{padding:9px 11px;text-align:left;color:var(--mu);font-weight:700;font-size:10px;
    text-transform:uppercase;letter-spacing:.07em;white-space:nowrap}}
tbody tr{{border-bottom:1px solid var(--bd);transition:background .1s}}
tbody tr:hover{{background:rgba(59,130,246,.07)}}
td{{padding:9px 11px;vertical-align:middle}}
.badge{{background:rgba(59,130,246,.15);color:var(--ac2);
        border:1px solid rgba(59,130,246,.35);padding:2px 8px;
        border-radius:4px;font-family:monospace;font-size:11px;font-weight:600;white-space:nowrap}}
.cam-name{{color:var(--mu);font-size:12px}}
.order-col{{font-family:monospace;color:var(--yw);font-size:12px}}
.bp{{background:var(--gn);color:#000;border:none;padding:5px 12px;
     border-radius:5px;cursor:pointer;font-weight:700;font-size:12px;margin-right:5px}}
.bp:hover{{background:#16a34a;color:#fff}}
.bd{{background:var(--panel);color:var(--ac2);border:1px solid var(--bd);
     padding:5px 12px;border-radius:5px;text-decoration:none;font-size:12px;font-weight:600}}
.bd:hover{{border-color:var(--ac)}}
#nr{{text-align:center;padding:48px;color:var(--mu);display:none;font-size:14px}}
.gen{{padding:0 24px 10px;color:var(--mu);font-size:10px;font-family:monospace}}
/* Modal */
#modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:999;
        align-items:center;justify-content:center}}
#modal.open{{display:flex}}
.mb{{background:var(--panel);border:1px solid var(--bd);border-radius:10px;
     padding:20px;max-width:900px;width:96%;position:relative}}
.mb-title{{font-size:11px;margin-bottom:12px;color:var(--ac2);font-family:monospace;word-break:break-all}}
.mb video{{width:100%;border-radius:6px;background:#000;max-height:520px}}
.cb{{position:absolute;top:10px;right:12px;background:var(--rd);color:#fff;
     border:none;border-radius:50%;width:26px;height:26px;cursor:pointer;
     font-weight:700;line-height:26px;text-align:center;font-size:14px}}
</style>
</head>
<body>

<header>
  <div class="logo">&#128249;</div>
  <div>
    <h1>CCTV AI System &ndash; Tra c&#7913;u Video</h1>
    <div class="sub">{base.replace(chr(92), '/')} &nbsp;|&nbsp; {index['generated_at'][:19]}</div>
  </div>
</header>

<div class="stats">
  <div class="sc"><div class="v" style="color:var(--ac)">{index['total']}</div><div class="l">T&#7893;ng video</div></div>
  <div class="sc"><div class="v" id="sf" style="color:var(--ac2)">&mdash;</div><div class="l">K&#7871;t qu&#7843; l&#7885;c</div></div>
  <div class="sc"><div class="v" style="color:var(--or)">{total_size:.1f} MB</div><div class="l">Dung l&#432;&#7907;ng</div></div>
  <div class="sc"><div class="v" style="color:var(--gn)">{len(set(v.get('camera_id','') for v in vids))}</div><div class="l">Camera IDs</div></div>
  <div class="sc"><div class="v" style="color:var(--yw)">{len(set(v.get('employee_id','') for v in vids if v.get('employee_id') not in ('NOEMP','',None)))}</div><div class="l">Nh&#226;n vi&#234;n</div></div>
</div>

<div class="filters">
  <input class="fi fi-kw"    id="kw"    type="text"  placeholder="&#128269; M&#227; &#273;&#417;n, nh&#226;n vi&#234;n, camera, file..." oninput="flt()">
  <select class="fi fi-cam"  id="fc"    onchange="flt()">
    <option value="">T&#7845;t c&#7843; camera</option>
    {cam_opts}
  </select>
  <input class="fi fi-date"  id="fd"    type="text"  placeholder="Ngày dd/mm/yyyy" oninput="flt()">
  <input class="fi fi-order" id="fo"    type="text"  placeholder="M&#227; &#273;&#417;n / QR..." oninput="flt()">
  <button class="rb" onclick="location.reload()">&#128260; L&#224;m m&#7899;i</button>
</div>

<div class="tw">
  <table>
    <thead>
      <tr>


        <th>ID camera</th>
        <th>Mã đơn</th>
        <th>Nhân viên</th>
        <th>Bộ phận</th>
        <th>Ngày</th>
        <th>Giờ</th>
        <th>Thời lượng</th>
        <th>Dung lượng</th>
        <th>Thao tác</th>


      </tr>
    </thead>
    <tbody id="tb">
      {rows if rows else empty_row}
    </tbody>
  </table>
  <div id="nr">Kh&#244;ng t&#236;m th&#7845;y video ph&#249; h&#7907;p v&#7899;i b&#7897; l&#7885;c.</div>
</div>

<div class="gen">Generated: {index['generated_at']} &nbsp;|&nbsp; Total: {index['total']} files</div>

<!-- Modal player -->
<div id="modal">
  <div class="mb">
    <button class="cb" onclick="cm()">&#10005;</button>
    <div class="mb-title" id="mt"></div>
    <video id="mv" controls autoplay></video>
  </div>
</div>

<script>
const R = Array.from(document.querySelectorAll('#tb tr[data-cam]'));
document.getElementById('sf').textContent = R.length;

function vnDateToIso(s) {{
  s = (s || '').trim();

  if (!s) return '';

  const p = s.split('/');

  if (p.length !== 3) return '__INVALID__';

  const d = p[0].padStart(2, '0');
  const m = p[1].padStart(2, '0');
  const y = p[2];

  if (y.length !== 4) return '__INVALID__';

  return `${{y}}-${{m}}-${{d}}`;
}}

function flt() {{
  const kw = document.getElementById('kw').value.toLowerCase();
  const fc = document.getElementById('fc').value;
  const fdText = document.getElementById('fd').value;
  const fd = vnDateToIso(fdText);
  const fo = document.getElementById('fo').value.toLowerCase();

  if (fd === '__INVALID__') {{
    R.forEach(r => r.style.display = 'none');
    document.getElementById('sf').textContent = 0;
    document.getElementById('nr').style.display = 'block';
    return;
  }}

  let n = 0;

  R.forEach(r => {{
    const ok =
      (!kw || r.textContent.toLowerCase().includes(kw)) &&
      (!fc || r.dataset.cam === fc) &&
      (!fd || r.dataset.date === fd) &&
      (!fo || r.dataset.order.includes(fo) || r.dataset.emp.includes(fo));

    r.style.display = ok ? '' : 'none';

    if (ok) n++;
  }});

  document.getElementById('sf').textContent = n;
  document.getElementById('nr').style.display = (n === 0 && R.length > 0) ? 'block' : 'none';
}}

function pv(url, name) {{
  document.getElementById('mt').textContent = '\u25b6 ' + name;
  const vid = document.getElementById('mv');
  vid.src = url;
  vid.load();
  document.getElementById('modal').classList.add('open');
}}

function cm() {{
  document.getElementById('modal').classList.remove('open');
  const v = document.getElementById('mv');
  v.pause(); v.src = '';
}}

document.getElementById('modal').addEventListener('click', function(e) {{
  if (e.target === this) cm();
}});

// Xử lý lỗi phát video
document.getElementById('mv').addEventListener('error', function() {{
  const t = document.getElementById('mt');
  t.textContent = t.textContent + ' \u2014 \u26a0\ufe0f Kh\u00f4ng th\u1ec3 ph\u00e1t (ki\u1ec3m tra \u0111\u01b0\u1eddng d\u1eabn ho\u1eb7c codec)';
}});
</script>
</body>
</html>"""

    html_path = os.path.join(base, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path
