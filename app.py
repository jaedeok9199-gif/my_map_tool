import streamlit as st
import requests
import folium
import pandas as pd
import streamlit.components.v1 as components

st.set_page_config(page_title="주소 변환 및 위치 비교 툴", page_icon="📍", layout="wide")

st.title("📍 주소 변환 및 매장 위치 비교")
st.caption("카카오 API를 연동하여 정교한 건물 위치를 탐색하고 설정한 반경 범위 내 기존 매장과 비교합니다.")

# ------------------------------------------------------------------
# [카카오 REST API 키 설정]
DEFAULT_KAKAO_KEY = "" 
# ------------------------------------------------------------------

# 사이드바 설정 영역
with st.sidebar:
    st.header("⚙️ 설정")
    user_kakao_key = st.text_input("카카오 REST API 키", value=DEFAULT_KAKAO_KEY, type="password")
    st.write("---")
    radius_km = st.slider("🔴 검색 위치 반경 설정 (km)", min_value=0.5, max_value=20.0, value=3.0, step=0.5)

# 기본 사이즈를 대폭(절반) 줄인 핀 생성 함수
def get_clean_pin(color_hex, is_search=False):
    # 일반 매장 6x9 (매우 작음), 검색 위치 10x14
    w, h = (10, 14) if is_search else (6, 9)
    svg = f'''
    <div class="custom-pin-icon" style="transition: transform 0.15s ease-out; transform-origin: bottom center;">
        <svg width="{w}" height="{h}" viewBox="0 0 24 34" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 0C5.37 0 0 5.37 0 12C0 21 12 34 12 34C12 34 24 21 24 12C24 5.37 18.63 0 12 0Z" fill="{color_hex}"/>
        </svg>
    </div>
    '''
    return svg

# CSV 파일 로드
@st.cache_data
def load_stores():
    try:
        df = pd.read_csv('stores.csv', encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv('stores.csv', encoding='cp949')
        
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lng'] = pd.to_numeric(df['lng'], errors='coerce')
    return df.dropna(subset=['lat', 'lng'])

try:
    stores_df = load_stores()
    st.sidebar.success(f"불러온 매장 수: {len(stores_df)}개")
except Exception as e:
    st.error(f"stores.csv 읽기 실패: {e}")
    stores_df = pd.DataFrame(columns=['name', 'lat', 'lng'])

# 카카오 지오코딩 함수
def get_kakao_coords(address, api_key):
    headers = {"Authorization": f"KakaoAK {api_key}"}
    url_addr = f"https://dapi.kakao.com/v2/local/search/address.json?query={address}"
    res = requests.get(url_addr, headers=headers)
    if res.status_code == 200 and res.json()['documents']:
        doc = res.json()['documents'][0]
        return float(doc['y']), float(doc['x']), doc.get('address_name', address)
        
    url_kw = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={address}"
    res_kw = requests.get(url_kw, headers=headers)
    if res_kw.status_code == 200 and res_kw.json()['documents']:
        doc = res_kw.json()['documents'][0]
        return float(doc['y']), float(doc['x']), doc.get('place_name', address)
        
    return None, None, None

address = st.text_input("검색할 주소를 입력하세요", placeholder="예: 성남시 중원구 희망로 415")
search_clicked = st.button("좌표 추출 및 위치 비교", type="primary")

search_lat, search_lng, found_name = None, None, None

if search_clicked:
    if not user_kakao_key:
        st.error("사이드바에 '카카오 REST API 키'를 입력해주세요!")
    elif address.strip():
        with st.spinner("카카오 위성 데이터 기반 정확한 좌표 탐색 중..."):
            search_lat, search_lng, found_name = get_kakao_coords(address, user_kakao_key)
            
            if search_lat and search_lng:
                st.success(f"변환 성공! [{found_name}]")
                col1, col2 = st.columns(2)
                col1.metric("위도 (Latitude)", f"{search_lat:.6f}")
                col2.metric("경도 (Longitude)", f"{search_lng:.6f}")
            else:
                st.error("주소를 찾을 수 없습니다.")

st.write("---")
st.subheader(f"🗺️ 위치 비교 지도 (🔴 검색 위치 반경 {radius_km}km / 🔵 기존 매장)")

if search_lat and search_lng:
    center_lat, center_lng = search_lat, search_lng
    zoom_level = 14 if radius_km <= 2 else (13 if radius_km <= 5 else 12)
elif not stores_df.empty:
    center_lat, center_lng, zoom_level = stores_df['lat'].mean(), stores_df['lng'].mean(), 11
else:
    center_lat, center_lng, zoom_level = 37.5665, 126.9780, 11

m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_level)

# 1. 기존 매장 마커 (그룹화 제거 -> 개별 마커로 지도에 직접 추가)
for _, row in stores_df.iterrows():
    folium.Marker(
        location=[row['lat'], row['lng']],
        popup=f"<b>{row['name']}</b>",
        tooltip=f"기존 매장: {row['name']}",
        icon=folium.DivIcon(
            html=get_clean_pin('#38BDF8', is_search=False),
            icon_size=(6, 9),
            icon_anchor=(3, 9) # 뾰족한 끝이 좌표에 정확히 맞도록 앵커 설정
        )
    ).add_to(m)

# 2. 검색 위치 마커 + 반경 원
if search_lat and search_lng:
    folium.Circle(
        location=[search_lat, search_lng],
        radius=radius_km * 1000,
        color='#F87171',
        fill=True,
        fill_color='#F87171',
        fill_opacity=0.15,
        weight=1.5
    ).add_to(m)

    folium.Marker(
        location=[search_lat, search_lng],
        popup=f"<b>[검색 위치]</b><br>{address}",
        tooltip=f"검색 위치: {address}",
        icon=folium.DivIcon(
            html=get_clean_pin('#F87171', is_search=True),
            icon_size=(10, 14),
            icon_anchor=(5, 14)
        )
    ).add_to(m)

# 지도 줌/아웃 시 마커 크기가 자동 연동되는 자바스크립트 주입 (스케일 수치 재조정)
zoom_script = """
<script>
document.addEventListener("DOMContentLoaded", function() {
    var checkExist = setInterval(function() {
        var mapElement = document.querySelector('.folium-map');
        if (mapElement && mapElement._leaflet_map) {
            var map = mapElement._leaflet_map;
            clearInterval(checkExist);
            
            function adjustMarkerScale() {
                var zoom = map.getZoom();
                // 전국 지도(Zoom 7)에서는 0.8배, 동네 지도(Zoom 16+)에서는 최대 3.5배까지 동적으로 커짐
                var scale = Math.max(0.8, Math.min(3.5, 0.8 + (zoom - 7) * 0.25));
                var pins = document.querySelectorAll('.custom-pin-icon');
                pins.forEach(function(pin) {
                    pin.style.transform = 'scale(' + scale + ')';
                });
            }
            
            map.on('zoomend', adjustMarkerScale);
            adjustMarkerScale();
        }
    }, 100);
});
</script>
"""

map_html = m._repr_html_() + zoom_script
components.html(map_html, height=580)
