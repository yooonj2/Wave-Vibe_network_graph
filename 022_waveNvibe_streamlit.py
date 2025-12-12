import streamlit as st
import pickle
import pandas as pd
from pyvis.network import Network
import streamlit.components.v1 as components
import os

# ==========================================
# 0. 설정 및 유틸리티 함수
# ==========================================
st.set_page_config(
    page_title="레시피 재료 네트워크", 
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_edge_color(weight):
    """가중치에 따라 투명도(alpha)를 조절하여 RGBA 색상을 반환"""
    if weight <= 50: alpha = 0.1
    elif weight <= 150: alpha = 0.3
    elif weight <= 300: alpha = 0.5
    elif weight <= 500: alpha = 0.7
    else: alpha = 1.0
    return f"rgba(100, 100, 100, {alpha})"

@st.cache_data
def load_data(filepath):
    with open(filepath, 'rb') as f:
        data = pickle.load(f)
    return data

# ==========================================
# 1. 데이터 로드
# ==========================================
# 실제 파일 경로에 맞게 수정해주세요
# 현재 실행 중인 파일(app.py)의 폴더 경로를 구함
current_dir = os.path.dirname(os.path.abspath(__file__))

# 경로 결합 (운영체제에 맞게 알아서 합쳐줌)
FILE_PATH = os.path.join(current_dir, "graphs.pkl")

try:
    data = load_data(FILE_PATH)
except FileNotFoundError:
    st.error(f"파일을 찾을 수 없습니다: {FILE_PATH}")
    st.stop()

# ==========================================
# 2. 사이드바 UI
# ==========================================
st.sidebar.header("📊 그래프 설정")

key_options = list(data.keys())
formatted_options = {f"{k[0]} ({k[1]})": k for k in key_options}
selected_label = st.sidebar.selectbox("카테고리 선택", options=list(formatted_options.keys()))
selected_key = formatted_options[selected_label]

st.sidebar.subheader("필터링 옵션")
limit_edges = st.sidebar.slider("표시할 최대 연결(Edge) 수", 100, 2000, 100, step=100)
min_node_count = st.sidebar.number_input("노드 최소 등장 횟수 (Count)", value=0, step=10)

# ==========================================
# 3. 데이터 추출 및 최적화
# ==========================================
raw_nodes = data[selected_key]['nodes']
raw_edges = data[selected_key]['edges']

if 'id' in raw_nodes.columns:
    raw_nodes = raw_nodes.set_index('id')
node_info_dict = raw_nodes.to_dict(orient='index')

df_edges_sorted = raw_edges.sort_values(by='weight', ascending=False).head(limit_edges)

# ==========================================
# 4. 네트워크 그래프 생성
# ==========================================
st.title(f"🍲 {selected_label} 네트워크 시각화")

net = Network(height="700px", width="100%", bgcolor="#ffffff", font_color="black")

added_nodes = set()
NODE_COLOR = '#FF9F1C'  # 기본 노드 색상 (오렌지)

# itertuples 사용 (속도 최적화)
for row in df_edges_sorted.itertuples():
    src = row.source
    dst = row.target
    w = row.weight
    
    # Source 노드 추가
    if src not in added_nodes:
        info = node_info_dict.get(src, {})
        count = info.get('count', 0)
        
        if count >= min_node_count:
            net.add_node(
                src, 
                label=src, 
                title=f"{src}\n(등장 횟수: {count})", 
                color=NODE_COLOR, 
                size=25,
                shape='circle',         # [변경] 글씨를 노드 안에 넣기 위해 circle 사용
                font={'color': 'white', 'size': 14} # [변경] 글씨 색상 및 기본 크기
            )
            added_nodes.add(src)
        
    # Target 노드 추가
    if dst not in added_nodes:
        info = node_info_dict.get(dst, {})
        count = info.get('count', 0)
        
        if count >= min_node_count:
            net.add_node(
                dst, 
                label=dst, 
                title=f"{dst}\n(등장 횟수: {count})", 
                color=NODE_COLOR, 
                size=25,
                shape='circle',         # [변경] 글씨를 노드 안에 넣기 위해 circle 사용
                font={'color': 'white', 'size': 14} # [변경] 글씨 색상 및 기본 크기
            )
            added_nodes.add(dst)
    
    # 엣지 추가
    if src in added_nodes and dst in added_nodes:
        color_rgba = get_edge_color(w)
        net.add_edge(src, dst, title=f"Weight: {w}", color=color_rgba)

# ==========================================
# 5. 물리 엔진 옵션
# ==========================================
net.set_options("""
var options = {
  "physics": {
    "barnesHut": {
      "gravitationalConstant": -500,
      "centralGravity": 0.3,
      "springLength": 150,
      "springConstant": 0.05,
      "damping": 0.09,
      "avoidOverlap": 0.1
    },
    "minVelocity": 0.75
  },
  "interaction": {
    "hover": true,
    "tooltipDelay": 200
  }
}
""")

# ==========================================
# 6. HTML 생성 및 JS 주입 (핵심 부분)
# ==========================================
path = os.path.join(os.getcwd(), "network_temp.html")
net.save_graph(path)

try:
    with open(path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # [Custom JS] 호버 시: 연결된 노드 확대 + 글씨 확대 + 나머지는 회색 처리
    js_event_code = """
    network.on("hoverNode", function (params) {
        var hoveredNodeId = params.node;
        var connectedNodeIds = network.getConnectedNodes(hoveredNodeId);
        
        // 연결된 노드 리스트에 현재 마우스 올린 노드도 포함 (빠른 검색을 위해 Set 사용)
        var connectedSet = new Set(connectedNodeIds);
        connectedSet.add(hoveredNodeId);
        
        var allNodeIds = nodes.getIds();
        var updates = [];
        
        allNodeIds.forEach(function(nodeId) {
            if (connectedSet.has(nodeId)) {
                // [연결된 노드] 강조: 크기 확대, 글씨 확대, 원래 색상 유지
                updates.push({
                    id: nodeId, 
                    size: 45, 
                    font: {size: 25, color: 'white'}, // 글씨도 같이 커짐
                    color: '#FF9F1C' 
                }); 
            } else {
                // [연결 안 된 노드] 흐리게: 회색 처리
                updates.push({
                    id: nodeId, 
                    color: '#E0E0E0', // 옅은 회색
                    font: {color: '#888888'} // 글씨도 흐리게 (선택사항)
                });
            }
        });
        
        nodes.update(updates);
    });

    network.on("blurNode", function (params) {
        var allNodeIds = nodes.getIds();
        var updates = [];
        
        // 마우스 떼면 모든 노드 원상복구
        allNodeIds.forEach(function(nodeId) {
            updates.push({
                id: nodeId, 
                size: 25,                 // 원래 크기
                font: {size: 14, color: 'white'}, // 원래 글씨 크기와 색상
                color: '#FF9F1C'          // 원래 색상
            }); 
        });
        
        nodes.update(updates);
    });
    
    return network;
    """
    
    if "return network;" in html_content:
        html_content = html_content.replace("return network;", js_event_code)
    else:
        html_content = html_content.replace("</body>", "<script>" + js_event_code.replace("return network;", "") + "</script></body>")

    components.html(html_content, height=720)
    st.caption(f"💡 현재 표시된 노드: {len(added_nodes)}개 | 마우스를 올리면 연결된 재료만 강조됩니다.")

except Exception as e:

    st.error(f"HTML 렌더링 중 오류 발생: {e}")


