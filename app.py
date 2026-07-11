from __future__ import annotations

import os

# pyarrow 25.x의 mimalloc 할당자가 macOS에서 스레드 초기화 중 segfault를 일으키므로
# pandas/streamlit이 libarrow를 로드하기 전에 시스템 할당자로 강제한다.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

import base64
import importlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import complaint_agents as complaint_agents_module


complaint_agents_module = importlib.reload(complaint_agents_module)
ComplaintSupervisor = complaint_agents_module.ComplaintSupervisor
DEFAULT_MODELS = complaint_agents_module.DEFAULT_MODELS
AGENT_SPECS = complaint_agents_module.AGENT_SPECS
AGENT_ROLE_GROUPS = complaint_agents_module.AGENT_ROLE_GROUPS
OpenRouterClient = complaint_agents_module.OpenRouterClient
OpenRouterError = complaint_agents_module.OpenRouterError
normalize_text = complaint_agents_module.normalize_text
create_runtime_store = complaint_agents_module.create_runtime_store

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_XLSX = BASE_DIR / "1782341096215_file.xlsx"
PIXEL_ASSET_DIR = BASE_DIR / "assets" / "pixel_office"

RESULT_SCHEMA_VERSION = 2

STATUS_LABELS = {
    "DRAFT_APPROVED": ("✅ 승인 초안 (담당자 검토 전)", "success"),
    "HUMAN_REVIEW_REQUIRED": ("🟡 사람 검토 필요", "warning"),
    "REJECTED": ("⛔ 자동 초안 거절", "error"),
    "INPUT_REJECTED": ("🚫 입력 거절", "error"),
}

ZONE_LABELS = {
    "intake_desk": "접수 데스크",
    "classification_cell": "분류 셀",
    "law_library": "법령 자료실",
    "case_room": "사례 검색실",
    "writing_desk": "작성석",
    "validation_room": "검증실",
    "supervisor_desk": "Supervisor",
    "meeting_room": "회의실",
    "human_review_desk": "사람 검토 창구",
}


def get_secret_api_key() -> str:
    """`.streamlit/secrets.toml`의 OPENROUTER_API_KEY를 읽는다. 없으면 빈 문자열."""
    try:
        return str(st.secrets.get("OPENROUTER_API_KEY", "")).strip()
    except Exception:  # noqa: BLE001 - secrets 파일 없음/파싱 오류 모두 키 없음으로 처리
        return ""


@st.cache_data(show_spinner=False)
def load_sample_data(path: str) -> pd.DataFrame:
    return pd.read_excel(path).fillna("")


def sample_label(df: pd.DataFrame, idx: int) -> str:
    row = df.iloc[idx]
    complaint_no = normalize_text(row.iloc[0])
    title = normalize_text(row.iloc[1])
    if len(title) > 54:
        title = title[:54] + "..."
    return f"{complaint_no} | {title}"


def set_sample(df: pd.DataFrame, idx: int) -> None:
    row = df.iloc[idx]
    st.session_state["complaint_title"] = normalize_text(row.iloc[1])
    st.session_state["complaint_body"] = normalize_text(row.iloc[2])
    st.session_state["complaint_no"] = normalize_text(row.iloc[0])


@st.cache_data(show_spinner=False)
def pixel_asset_data_uri(relative_path: str) -> str:
    path = PIXEL_ASSET_DIR / relative_path
    if not path.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def build_idle_runtime_snapshot(model_settings: dict[str, str]) -> dict[str, Any]:
    """실행 전 대기 상태의 12-Agent snapshot."""
    return create_runtime_store("ready", model_settings).to_snapshot()


ZONE_LAYOUT = {
    # 논리 좌표(고정): x, y, w, h — Canvas는 컨테이너 크기에 맞춰 스케일한다.
    "intake_desk": (16, 44, 170, 140),
    "classification_cell": (200, 44, 210, 140),
    "law_library": (424, 44, 148, 140),
    "case_room": (586, 44, 148, 140),
    "supervisor_desk": (748, 44, 138, 140),
    "writing_desk": (16, 208, 196, 150),
    "validation_room": (226, 208, 230, 150),
    "meeting_room": (470, 208, 190, 150),
    "human_review_desk": (674, 208, 212, 150),
}

TEAM_CHAR_INDEX = {
    "intake": 0,
    "classification": 1,
    "evidence": 2,
    "writing": 3,
    "validation": 4,
    "publishing": 5,
}


def _json_for_html(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def render_pixel_office(snapshot: dict[str, Any]) -> None:
    agents = snapshot.get("agents") or []
    if not agents:
        st.info("Pixel snapshot이 비어 있습니다.")
        return

    assets = {
        "floor": pixel_asset_data_uri("floors/floor_1.png"),
        "wall": pixel_asset_data_uri("walls/wall_0.png"),
        "desk": pixel_asset_data_uri("furniture/DESK/DESK_FRONT.png"),
        "pc_on": pixel_asset_data_uri("furniture/PC/PC_FRONT_ON_1.png"),
        "pc_off": pixel_asset_data_uri("furniture/PC/PC_FRONT_OFF.png"),
        "bookshelf": pixel_asset_data_uri("furniture/BOOKSHELF/BOOKSHELF.png"),
        "plant": pixel_asset_data_uri("furniture/LARGE_PLANT/LARGE_PLANT.png"),
        "whiteboard": pixel_asset_data_uri("furniture/WHITEBOARD/WHITEBOARD.png"),
        "clock": pixel_asset_data_uri("furniture/CLOCK/CLOCK.png"),
        "characters": [pixel_asset_data_uri(f"characters/char_{i}.png") for i in range(6)],
    }

    payload = {
        "agents": [
            {
                "agent_id": a.get("agent_id"),
                "display_name": a.get("display_name"),
                "team": a.get("team"),
                "status": a.get("status"),
                "zone": a.get("zone"),
                "target_zone": a.get("target_zone"),
                "activity": a.get("activity"),
                "summary": str(a.get("last_safe_summary") or "")[:40],
                "char": TEAM_CHAR_INDEX.get(a.get("team"), 0),
            }
            for a in agents
        ],
        "events": [
            {
                "seq": e.get("seq"),
                "type": e.get("type"),
                "agent_id": e.get("agent_id"),
                "from_zone": e.get("from_zone"),
                "to_zone": e.get("to_zone"),
            }
            for e in (snapshot.get("events") or [])[-60:]
        ],
        "zones": ZONE_LAYOUT,
        "zoneLabels": ZONE_LABELS,
        "assets": assets,
        "traceId": snapshot.get("trace_id", ""),
    }

    office_html = """
<div id="office-wrap" style="width:100%;">
  <canvas id="office" style="width:100%; display:block; image-rendering:pixelated;
    border:4px solid #1b1d35; box-shadow:0 8px 0 #0e1020; background:#14172b;"></canvas>
</div>
<script>
const DATA = __PAYLOAD__;
const W = 900, H = 372;
const canvas = document.getElementById('office');
const ctx = canvas.getContext('2d');
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const STATUS_COLORS = {
  waiting: '#8f95b5', moving: '#58c7f0', active: '#59e08b',
  blocked: '#f4c14e', error: '#f06a6a', done: '#a7f070'
};
const ACTIVITY_ICON = {
  typing: '⌨', reading: '📖', handoff: '📄', reviewing: '🔍',
  meeting: '👥', alert: '⚠', walking: '👣', idle: ''
};

const images = {};
function loadImage(key, uri) {
  if (!uri) return;
  const img = new Image();
  img.src = uri;
  images[key] = img;
}
loadImage('floor', DATA.assets.floor);
loadImage('wall', DATA.assets.wall);
loadImage('desk', DATA.assets.desk);
loadImage('pc_on', DATA.assets.pc_on);
loadImage('pc_off', DATA.assets.pc_off);
loadImage('bookshelf', DATA.assets.bookshelf);
loadImage('plant', DATA.assets.plant);
loadImage('whiteboard', DATA.assets.whiteboard);
loadImage('clock', DATA.assets.clock);
DATA.assets.characters.forEach((uri, i) => loadImage('char' + i, uri));

function zoneSlots(zoneName) {
  return DATA.agents.filter(a => a.zone === zoneName).map(a => a.agent_id);
}
function agentTarget(agent) {
  const zone = DATA.zones[agent.zone] || DATA.zones['supervisor_desk'];
  const [zx, zy, zw, zh] = zone;
  const siblings = zoneSlots(agent.zone);
  const idx = Math.max(0, siblings.indexOf(agent.agent_id));
  const cols = Math.max(1, Math.floor(zw / 56));
  const col = idx % cols, row = Math.floor(idx / cols);
  return { x: zx + 30 + col * 56, y: zy + 58 + row * 44 };
}

const positions = {};
DATA.agents.forEach(a => { positions[a.agent_id] = agentTarget(a); });

// handoff 종이: 최근 handoffProduced 이벤트를 순차 재생
const handoffs = DATA.events
  .filter(e => e.type === 'handoffProduced')
  .slice(-6)
  .map((e, i) => {
    const fromAgent = DATA.agents.find(a => a.agent_id === e.agent_id);
    const fromZone = e.from_zone || (fromAgent ? fromAgent.zone : 'supervisor_desk');
    const toZone = e.to_zone || 'supervisor_desk';
    return { from: fromZone, to: toZone, delay: i * 900 };
  });
const startTime = performance.now();

function zoneCenter(name) {
  const z = DATA.zones[name] || DATA.zones['supervisor_desk'];
  return { x: z[0] + z[2] / 2, y: z[1] + z[3] / 2 };
}

function fitCanvas() {
  const wrap = document.getElementById('office-wrap');
  const cssWidth = Math.max(320, wrap.clientWidth);
  const scale = cssWidth / W;
  canvas.width = W * window.devicePixelRatio * Math.min(scale, 1.4);
  canvas.height = H * window.devicePixelRatio * Math.min(scale, 1.4);
  canvas.style.height = (H * scale) + 'px';
}
fitCanvas();
window.addEventListener('resize', () => { fitCanvas(); });

function drawZone(name) {
  const [x, y, w, h] = DATA.zones[name];
  ctx.fillStyle = 'rgba(27,29,53,0.55)';
  ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = '#3f456d';
  ctx.lineWidth = 2;
  ctx.strokeRect(x, y, w, h);
  ctx.fillStyle = '#b6c4ff';
  ctx.font = 'bold 12px "Segoe UI", sans-serif';
  ctx.fillText(DATA.zoneLabels[name] || name, x + 6, y + 16);
}

function drawFurniture() {
  const desk = images['desk'];
  for (const name of Object.keys(DATA.zones)) {
    const [x, y, w, h] = DATA.zones[name];
    if (desk && desk.complete && desk.naturalWidth) {
      ctx.drawImage(desk, x + w / 2 - 24, y + 22, 48, 24);
    } else {
      ctx.fillStyle = '#8a5a2b';
      ctx.fillRect(x + w / 2 - 24, y + 26, 48, 16);
    }
  }
  const deco = [['bookshelf', 430, 6, 40, 34], ['plant', 20, 6, 22, 34],
                ['whiteboard', 480, 6, 46, 30], ['clock', 620, 8, 16, 16]];
  for (const [key, x, y, w, h] of deco) {
    const img = images[key];
    if (img && img.complete && img.naturalWidth) ctx.drawImage(img, x, y, w, h);
  }
}

function drawAgent(agent, now) {
  const target = agentTarget(agent);
  const pos = positions[agent.agent_id];
  if (reduceMotion) {
    pos.x = target.x; pos.y = target.y;
  } else {
    pos.x += (target.x - pos.x) * 0.12;
    pos.y += (target.y - pos.y) * 0.12;
  }
  const movingNow = Math.abs(target.x - pos.x) + Math.abs(target.y - pos.y) > 1.5;
  const frame = (!reduceMotion && (movingNow || agent.status === 'active'))
    ? Math.floor(now / 260) % 2 : 0;

  const charImg = images['char' + agent.char];
  if (charImg && charImg.complete && charImg.naturalWidth) {
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(charImg, frame * 16, 0, 16, 32, pos.x - 16, pos.y - 44, 32, 64);
  } else {
    // asset 누락 fallback: 팀 색상 픽셀 도형 캐릭터
    ctx.fillStyle = STATUS_COLORS[agent.status] || '#8f95b5';
    ctx.fillRect(pos.x - 10, pos.y - 34, 20, 26);
    ctx.fillStyle = '#f6e0c8';
    ctx.fillRect(pos.x - 7, pos.y - 44, 14, 12);
  }

  // 상태 점 + 활동 아이콘
  ctx.fillStyle = STATUS_COLORS[agent.status] || '#8f95b5';
  ctx.beginPath();
  ctx.arc(pos.x + 14, pos.y - 40, 5, 0, Math.PI * 2);
  ctx.fill();
  const icon = ACTIVITY_ICON[agent.activity] || '';
  if (icon) {
    ctx.font = '13px "Segoe UI", sans-serif';
    ctx.fillText(icon, pos.x + 10, pos.y - 48);
  }

  // 이름표 (긴 한글은 Canvas 텍스트로 안전 출력)
  ctx.font = 'bold 11px "Segoe UI", sans-serif';
  ctx.fillStyle = '#f6f6ff';
  ctx.textAlign = 'center';
  ctx.fillText(agent.display_name, pos.x, pos.y + 14);
  ctx.textAlign = 'left';
}

function drawHandoffs(now) {
  if (reduceMotion) return;
  const elapsed = now - startTime;
  for (const h of handoffs) {
    const t = (elapsed - h.delay) / 1400;
    if (t < 0 || t > 1) continue;
    const from = zoneCenter(h.from), to = zoneCenter(h.to);
    const x = from.x + (to.x - from.x) * t;
    const y = from.y + (to.y - from.y) * t - Math.sin(t * Math.PI) * 22;
    ctx.fillStyle = '#fff7d6';
    ctx.strokeStyle = '#252747';
    ctx.lineWidth = 2;
    ctx.fillRect(x - 8, y - 6, 16, 12);
    ctx.strokeRect(x - 8, y - 6, 16, 12);
    ctx.strokeStyle = '#6a6f91';
    ctx.beginPath();
    ctx.moveTo(x - 5, y - 2); ctx.lineTo(x + 5, y - 2);
    ctx.moveTo(x - 5, y + 2); ctx.lineTo(x + 5, y + 2);
    ctx.stroke();
  }
}

function draw(now) {
  const scaleX = canvas.width / W, scaleY = canvas.height / H;
  ctx.setTransform(scaleX, 0, 0, scaleY, 0, 0);
  ctx.clearRect(0, 0, W, H);

  // 벽/바닥
  const wall = images['wall'], floor = images['floor'];
  if (wall && wall.complete && wall.naturalWidth) {
    const pat = ctx.createPattern(wall, 'repeat');
    ctx.fillStyle = pat;
  } else {
    ctx.fillStyle = '#343854';
  }
  ctx.fillRect(0, 0, W, 40);
  if (floor && floor.complete && floor.naturalWidth) {
    const pat = ctx.createPattern(floor, 'repeat');
    ctx.fillStyle = pat;
  } else {
    ctx.fillStyle = '#22263f';
  }
  ctx.fillRect(0, 40, W, H - 40);

  for (const name of Object.keys(DATA.zones)) drawZone(name);
  drawFurniture();
  for (const agent of DATA.agents) drawAgent(agent, now);
  drawHandoffs(now);

  if (!reduceMotion) requestAnimationFrame(draw);
}

if (reduceMotion) {
  // 이동을 즉시 반영하고 반복 애니메이션을 중단한다.
  draw(0);
  setInterval(() => draw(performance.now()), 1500);
} else {
  requestAnimationFrame(draw);
}
</script>
"""
    office_html = office_html.replace("__PAYLOAD__", _json_for_html(payload))
    components.html(office_html, height=400, scrolling=False)


def render_pixel_runtime(snapshot: dict[str, Any], *, key_hint: str = "runtime") -> None:
    render_pixel_office(snapshot)
    events = snapshot.get("events") or []
    if not events:
        return
    with st.expander("Pixel 이벤트 로그", expanded=False):
        rows = [
            {
                "seq": event.get("seq"),
                "timestamp": event.get("timestamp"),
                "type": event.get("type"),
                "agent": event.get("agent_id") or "",
                "from": event.get("from_zone") or "",
                "to": event.get("to_zone") or "",
                "summary": event.get("safe_summary", ""),
            }
            for event in events
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=280)


def render_final_output(final_output: dict[str, Any]) -> None:
    status = final_output.get("status", "HUMAN_REVIEW_REQUIRED")
    label, tone = STATUS_LABELS.get(status, (status, "warning"))
    if tone == "success":
        st.success(label)
    elif tone == "warning":
        st.warning(label)
    else:
        st.error(label)
    st.caption(f"{final_output.get('disclaimer', '')} · trace: {final_output.get('trace_id', '')}")

    if status == "DRAFT_APPROVED":
        st.markdown(final_output.get("answer") or "")
    else:
        st.markdown("승인된 답변 초안이 없습니다. 아래 사유를 담당자가 확인해야 합니다.")
        for reason in final_output.get("review_reasons", []):
            st.markdown(f"- {reason}")
        review_items = final_output.get("review_items") or []
        if review_items:
            with st.expander("담당자 확인 항목", expanded=True):
                for item in review_items:
                    st.markdown(f"- {item}")

    citations = final_output.get("citations") or []
    if citations:
        with st.expander("확인 가능한 출처", expanded=status != "DRAFT_APPROVED"):
            for url in citations:
                st.markdown(f"- {url}")


def build_download_payload(result: dict[str, Any]) -> str:
    """화면과 동일한 FinalOutput + 비민감 trace만 포함한다."""
    payload = {
        "schema_version": result.get("schema_version"),
        "final_output": result.get("final_output"),
        "manifest": result.get("manifest"),
        "state_history": result.get("state_history"),
        "supervisor_decisions": (result.get("supervisor") or {}).get("decisions"),
        "events": (result.get("pixel_runtime") or {}).get("events"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_results(result: dict[str, Any]) -> None:
    final_output = result.get("final_output") or {}

    st.subheader("최종 판정")
    render_final_output(final_output)

    st.download_button(
        "FinalOutput + trace 다운로드",
        data=build_download_payload(result),
        file_name=f"minwon_final_{result.get('trace_id', 'result')}.json",
        mime="application/json",
        width="stretch",
    )

    artifacts = result.get("artifacts") or {}
    tabs = st.tabs(
        [
            "Pixel Runtime",
            "검증 보고서",
            "수정 이력",
            "단계 산출물",
            "상태·handoff",
            "Supervisor",
        ]
    )

    with tabs[0]:
        runtime_snapshot = result.get("pixel_runtime")
        if runtime_snapshot:
            render_pixel_runtime(runtime_snapshot, key_hint="result")
        else:
            st.info("Pixel runtime 기록이 없습니다. 새로 실행하면 표시됩니다.")

    with tabs[1]:
        report = artifacts.get("validation_report") or final_output.get("validation_report")
        if report:
            validation_not_run = bool(report.get("note")) and not artifacts.get("validation_report")
            decision = "NOT RUN" if validation_not_run else report.get("decision", "-")
            validated_at = "미실행" if validation_not_run else report.get("validated_at", "-")
            st.markdown(f"**최종 판정: `{decision}`** · 검증 시각: {validated_at}")
            if validation_not_run:
                st.info(report.get("note") or "선행 단계에서 조기 종료되어 검증을 실행하지 않았습니다.")
            checks = report.get("checks") or {}
            if checks:
                cols = st.columns(len(checks))
                for col, (name, value) in zip(cols, checks.items()):
                    col.metric(name, "NOT RUN" if validation_not_run else value)
            findings = report.get("findings") or []
            if findings:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "severity": f.get("severity"),
                                "category": f.get("category", ""),
                                "message": f.get("message"),
                                "fix": f.get("fix"),
                            }
                            for f in findings
                        ]
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
            elif not validation_not_run:
                st.caption("finding 없음")
        else:
            st.info("검증 단계에 도달하지 못했습니다.")

    with tabs[2]:
        revision_history = result.get("revision_history") or []
        draft = artifacts.get("draft_package")
        if draft:
            st.markdown(f"**최종 revision_count: {draft.get('revision_count', 0)}**")
        if revision_history:
            for item in revision_history:
                with st.expander(f"수정 {item.get('revision', 0) + 1}차 지시", expanded=False):
                    for inst in item.get("instructions", []):
                        st.markdown(f"- {inst}")
        else:
            st.caption("수정 반복 없이 처리되었습니다.")
        if draft:
            with st.expander("주장-근거 매핑", expanded=False):
                st.json(draft.get("claim_evidence_map", []), expanded=True)

    with tabs[3]:
        order = [
            ("intake_result", "01 IntakeResult"),
            ("classification_result", "02 ClassificationResult"),
            ("evidence_package", "03 EvidencePackage"),
            ("draft_package", "04 DraftPackage"),
            ("validation_report", "05 ValidationReport"),
            ("final_output", "06 FinalOutput"),
        ]
        for key, label in order:
            payload = artifacts.get(key)
            with st.expander(label, expanded=False):
                if payload is None:
                    st.caption("실행되지 않음 (manifest의 skipped_stages 참고)")
                else:
                    st.json(payload, expanded=False)

    with tabs[4]:
        st.markdown("#### 상태 전이 이력")
        st.dataframe(
            pd.DataFrame(result.get("state_history") or []),
            hide_index=True,
            use_container_width=True,
        )
        manifest = result.get("manifest") or {}
        st.markdown("#### Trace 파일")
        st.code("\n".join(manifest.get("files", [])) or "없음", language="text")
        skipped = manifest.get("skipped_stages") or {}
        if skipped:
            st.markdown("#### 실행하지 않은 단계")
            for stage, reason in skipped.items():
                st.markdown(f"- `{stage}`: {reason}")

    with tabs[5]:
        supervisor = result.get("supervisor") or {}
        st.markdown(f"**정책**: {supervisor.get('policy', '')}")
        st.markdown("#### Supervisor 결정")
        st.dataframe(
            pd.DataFrame(supervisor.get("decisions") or []),
            hide_index=True,
            use_container_width=True,
        )
        with st.expander("도구 레지스트리 (requires/provides)", expanded=False):
            st.json(supervisor.get("tool_registry") or [], expanded=False)


def run_pipeline(
    *,
    api_key: str,
    complaint_id: str,
    title: str,
    body: str,
    model_settings: dict[str, str],
    max_results: int,
    read_pages: bool,
) -> dict[str, Any] | None:
    client = OpenRouterClient(api_key)
    supervisor = ComplaintSupervisor(
        client,
        model_settings=model_settings,
        max_results_per_category=max_results,
        read_pages=read_pages,
    )

    runtime_slot = st.empty()

    def render_runtime_snapshot(snapshot: dict[str, Any]) -> None:
        with runtime_slot.container():
            render_pixel_runtime(snapshot, key_hint="live")

    render_runtime_snapshot(supervisor.runtime.to_snapshot())

    try:
        with st.spinner("Supervisor가 12개 Agent 파이프라인을 실행하는 중..."):
            result = supervisor.run(
                complaint_id=complaint_id or "MANUAL",
                title=title,
                body=body,
                on_event=render_runtime_snapshot,
            )
    except OpenRouterError as exc:
        render_runtime_snapshot(supervisor.runtime.to_snapshot())
        st.error(str(exc))
        return None
    except Exception as exc:  # noqa: BLE001
        render_runtime_snapshot(supervisor.runtime.to_snapshot())
        st.error(f"실행 중 오류가 발생했습니다: {exc}")
        return None

    runtime_slot.empty()
    return result


def main() -> None:
    st.set_page_config(
        page_title="민원 초안 생성 멀티에이전트 오피스",
        page_icon="M",
        layout="wide",
    )

    st.title("민원 초안 생성 멀티에이전트 오피스")
    st.caption(
        "12개 업무 Agent가 입력 → 처리 → 독립 검증 → 출력 흐름으로 민원 답변 초안을 만듭니다. "
        "모든 결과는 담당자 검토 전 초안입니다."
    )

    if not SAMPLE_XLSX.exists():
        st.error(f"샘플 엑셀 파일을 찾을 수 없습니다: {SAMPLE_XLSX}")
        return

    df = load_sample_data(str(SAMPLE_XLSX))
    if "complaint_title" not in st.session_state:
        set_sample(df, 0)

    # 버전 필드가 없는 이전 결과는 폐기한다 (마이그레이션 규칙).
    last_result = st.session_state.get("last_result")
    if isinstance(last_result, dict) and last_result.get("schema_version") != RESULT_SCHEMA_VERSION:
        st.session_state.pop("last_result", None)
        last_result = None

    with st.sidebar:
        st.header("설정")
        secret_api_key = get_secret_api_key()
        api_key = st.text_input(
            "OpenRouter API Key",
            type="password",
            placeholder="미입력 시 .streamlit/secrets.toml 사용" if secret_api_key else "sk-or-...",
        )
        if not api_key.strip() and secret_api_key:
            api_key = secret_api_key
            st.caption("🔐 secrets.toml의 OPENROUTER_API_KEY를 사용합니다.")
        max_results = st.slider("검색 결과 수", min_value=2, max_value=8, value=5, step=1)
        read_pages = st.checkbox("검색 결과 본문 일부 읽기", value=True)

        st.subheader("역할군 모델")
        model_settings: dict[str, str] = {
            "classification": st.text_input("분류 역할군", value=DEFAULT_MODELS["classification"]),
            "search": st.text_input("검색 역할군", value=DEFAULT_MODELS["search"]),
            "writing": st.text_input("작성 역할군", value=DEFAULT_MODELS["writing"]),
            "review": st.text_input("검증 역할군", value=DEFAULT_MODELS["review"]),
        }
        with st.expander("고급: Agent별 모델 override", expanded=False):
            llm_agents = [
                spec for spec in AGENT_SPECS
                if spec.agent_id not in (
                    "intake-agent", "evidence-search-agent",
                    "response-validator-agent", "output-publisher-agent",
                )
            ]
            for spec in llm_agents:
                override = st.text_input(
                    f"{spec.display_name} ({spec.agent_id})",
                    value="",
                    placeholder=f"기본: {model_settings[AGENT_ROLE_GROUPS[spec.agent_id]]}",
                    key=f"override-{spec.agent_id}",
                )
                if override.strip():
                    model_settings[spec.agent_id] = override.strip()

    st.markdown("### Pixel Agents Office")
    preview_snapshot = (
        last_result.get("pixel_runtime") if isinstance(last_result, dict) else None
    )
    office_slot = st.empty()
    with office_slot.container():
        render_pixel_office(preview_snapshot or build_idle_runtime_snapshot(model_settings))

    left, right = st.columns([0.34, 0.66], gap="large")

    with left:
        st.subheader("엑셀 샘플")
        selected_idx = st.selectbox(
            "민원 선택",
            options=list(range(len(df))),
            format_func=lambda idx: sample_label(df, idx),
        )
        if st.button("선택 민원 불러오기", width="stretch"):
            set_sample(df, selected_idx)
            st.session_state.pop("last_result", None)
            st.rerun()

        st.dataframe(df.iloc[:, :2], width="stretch", hide_index=True, height=360)

    with right:
        st.subheader("민원 입력")
        title = st.text_input("제목", key="complaint_title")
        body = st.text_area("본문", key="complaint_body", height=280)
        run_clicked = st.button("Supervisor 실행", type="primary", width="stretch")

    if run_clicked:
        # 재실행 시 이전 결과·화면을 초기화해 다른 실행과 섞이지 않게 한다.
        st.session_state.pop("last_result", None)
        office_slot.empty()
        if not api_key.strip():
            st.error("OpenRouter API 키를 입력하세요.")
        else:
            result = run_pipeline(
                api_key=api_key,
                complaint_id=st.session_state.get("complaint_no", "MANUAL"),
                title=title,
                body=body,
                model_settings=model_settings,
                max_results=max_results,
                read_pages=read_pages,
            )
            if result:
                st.session_state["last_result"] = result
                with office_slot.container():
                    render_pixel_office(result.get("pixel_runtime") or {})
                render_results(result)
    elif isinstance(st.session_state.get("last_result"), dict):
        render_results(st.session_state["last_result"])


if __name__ == "__main__":
    main()
