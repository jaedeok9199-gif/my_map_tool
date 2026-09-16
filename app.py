import streamlit as st
import requests
import folium
from folium.plugins import HeatMap
import pandas as pd
import numpy as np
import json
import math
import re
from shapely.geometry import shape, mapping
from shapely.ops import transform
import streamlit.components.v1 as components

# ==========================================
# 1. 페이지 및 모던 UI 설정
# ==========================================
st.set_page_config(page_title="신규 업체 입점 검토 및 상권 분석", page_icon="📍", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F9FAFB; font-family: 'Pretendard', sans-serif; }
    #MainMenu, header, footer {visibility: hidden;}
    h1 { font-weight: 800; color: #111827; letter-spacing: -0.5px; margin-bottom: 0rem; }
    .st-emotion-cache-16idsys p { color: #6B7280; font-size: 1.1rem; margin-top: 0.5rem; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; background-color: #2563EB; color: white; border: none; padding: 0.6rem 1rem; transition: all 0.2s; }
    .stButton>button:hover { background-color: #1D4ED8; transform: translateY(-1px); }
    .stTextInput>div>div>input { border-radius: 8px; border: 1px solid #D1D5DB; padding: 0.6rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 복잡한 좌표 변환 함수
# ==========================================
def convert_coord(x, y, z=None):
    if 120.0 <= x <= 135.0 and 30.0 <= y <= 45.0: return (x, y, z) if z is not None else (x, y)
    if 30.0 <= x <= 45.0 and 120.0 <= y <= 135.0: return (y, x, z) if z is not None else (y, x)
    if 1000000.0 <= x <= 2300000.0 and 500000.0 <= y <= 1500000.0: x, y = y, x

    if 500000.0 <= x <= 1500000.0 and 1000000.0 <= y <= 2300000.0:
        a, f = 6378137.0, 1.0 / 298.257222101
        b = a * (1.0 - f)
        e2, e12 = (a**2 - b**2) / (a**2), (a**2 - b**2) / (b**2)
        lat_0, lon_0 = math.radians(38.0), math.radians(127.5)
        k_0, x_0, y_0 = 0.9996, 1000000.0, 2000000.0
        x_adj, y_adj = x - x_0, y - y_0
        M0 = a * ((1 - e2/4 - 3*e2**2/64 - 5*e2**3/256) * lat_0 - (3*e2/8 + 3*e2**2/32 + 45*e2**3/1024) * math.sin(2*lat_0) + (15*e2**2/256 + 45*e2**3/1024) * math.sin(4*lat_0) - (35*e2**3/3072) * math.sin(6*lat_0))
        M = M0 + y_adj / k_0
        mu = M / (a * (1 - e2/4 - 3*e2**2/64 - 5*e2**3/256))
        e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
        phi1 = mu + (3*e1/2 - 27*e1**3/32) * math.sin(2*mu) + (21*e1**2/16 - 55*e1**4/32) * math.sin(4*mu) + (151*e1**3/96) * math.sin(6*mu)
        N1 = a / math.sqrt(1 - e2 * math.sin(phi1)**2)
        T1, C1 = math.tan(phi1)**2, e12 * math.cos(phi1)**2
        R1 = a * (1 - e2) / ((1 - e2 * math.sin(phi1)**2)**1.5)
        D = x_adj / (N1 * k_0)
        lat = phi1 - (N1 * math.tan(phi1) / R1) * (D**2/2 - (5 + 3*T1 + 10*C1 - 4*C1**2 - 9*e12) * D**4/24 + (61 + 90*T1 + 298*C1 + 45*T1**2 - 252*e12 - 3*C1**2) * D**6/720)
        lon = lon_0 + (D - (1 + 2*T1 + C1) * D**3/6 + (5 - 2*C1 + 28*T1 - 3*C1**2 + 8*e12 + 24*T1**2) * D**5/120) / math.cos(phi1)
        return (math.degrees(lon), math.degrees(lat), z) if z is not None else (math.degrees(lon), math.degrees(lat))

    return (x, y, z) if z is not None else (x, y)

def _clean_str(val): return "" if pd.isna(val) else str(val).split('.')[0].strip()
def _extract_dong_name(text):
    if not text: return ""
    m = re.search(r'([가-힣0-9]+(?:동|읍|면)(?:[0-9]*가)?)', str(text).strip())
    return m.group(1) if m else str(text).strip()

def get_clean_pin(color_hex, is_search=False):
    w, h = (20, 28) if is_search else (12, 18)
    svg = f'''
    <div class="custom-pin-icon" style="transition: transform 0.15s ease-out; transform-origin: bottom center;">
        <svg width="{w}" height="{h}" viewBox="0 0 24 34" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 0C5.37 0 0 5.37 0 12C0 21 12 34 12 34C12 34 24 21 24 12C24 5.37 18.63 0 12 0Z" fill="{color_hex}"/>
        </svg>
    </div>
    '''
    return svg

# ==========================================
# 3. 데이터 로드 및 캐싱
# ==========================================
@st.cache_data
def load_and_process_data():
    df = pd.DataFrame()
    for enc in ['utf-8', 'euc-kr', 'cp949', 'utf-16', 'latin-1', 'utf-8-sig']:
        try:
            df = pd.read_csv('시공점.csv', encoding=enc)
            break
        except: continue
        
    if df.empty:
        for enc in ['utf-8', 'euc-kr', 'cp949']:
            try:
                df = pd.read_csv('stores.csv', encoding=enc)
                break
            except: continue

    if not df.empty:
        col_map = {'업체코드':'code', '업체명':'name', '위도':'lat', '경도':'lng', '월평균 예약 수':'avg_monthly_reservations', '월평균예약수':'avg_monthly_reservations', '재구매율':'repurchase_rate', '익일배송여부':'next_day_delivery', '활성 여부':'is_active', '활성여부':'is_active'}
        df = df.rename(columns=col_map)
        df['lat'] = pd.to_numeric(df.get('lat', []), errors='coerce')
        df['lng'] = pd.to_numeric(df.get('lng', []), errors='coerce')
        df = df.dropna(subset=['lat', 'lng']).reset_index(drop=True)
        df['code'] = df.get('code', '없음').fillna('없음').astype(str)
        df['name'] = df.get('name', '없음').fillna('없음').astype(str)
        df['is_active'] = df.get('is_active', 'Y').fillna('Y').astype(str).str.upper()
        df['avg_monthly_reservations'] = pd.to_numeric(df.get('avg_monthly_reservations', 0).astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['repurchase_rate'] = pd.to_numeric(df.get('repurchase_rate', 0).astype(str).str.replace('%', ''), errors='coerce').fillna(0)

    heat_points, simplified_geojson = [], None
    try:
        pop_df = pd.DataFrame()
        for enc in ['utf-8', 'utf-8-sig', 'euc-kr', 'cp949']:
            try:
                pop_df = pd.read_csv('인구.csv', encoding=enc)
                break
            except: continue
            
        if not pop_df.empty:
            pop_col = [c for c in pop_df.columns if '인구' in c]
            name_col = [c for c in pop_df.columns if any(k in c for k in ['동', '명', '이름', '지역', '행정'])]
            
            p_col = pop_col[0] if pop_col else pop_df.columns[-1]
            n_col = name_col[0] if name_col else pop_df.columns[0]

            pop_df['population'] = pd.to_numeric(pop_df[p_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            pop_df['name_clean'] = pop_df[n_col].astype(str).str.replace(' ', '').str.strip()
            pop_df['short_dong'] = pop_df[n_col].astype(str).apply(_extract_dong_name)
            
            full_name_map = pop_df.groupby('name_clean')['population'].sum().to_dict()
            short_dong_map = pop_df.groupby('short_dong')['population'].sum().to_dict()

            with open('행정동경계.geojson', 'r', encoding='utf-8') as f: gj = json.load(f)
            features, raw_points = [], []
            
            for idx, feat in enumerate(gj.get('features', [])):
                props = feat.get('properties', {})
                geo_name = ""
                for k in ['ADM_NM', 'adm_nm', 'EMD_NM', 'EMD_KOR_NM', 'dong', 'name', 'NAME']:
                    if k in props and props[k]:
                        geo_name = str(props[k]).strip()
                        break
                        
                geo_name_clean = geo_name.replace(' ', '')
                short_geo_dong = _extract_dong_name(geo_name)
                
                matched_pop = full_name_map.get(geo_name_clean, 0)
                if matched_pop == 0:
                    matched_pop = short_dong_map.get(short_geo_dong, 0)
                    
                try:
                    raw_geom = shape(feat['geometry'])
                    wgs_geom = transform(convert_coord, raw_geom)
                    simple_geom = wgs_geom.simplify(0.001, preserve_topology=True)
                    centroid = wgs_geom.centroid
                    
                    area_sq_km = max((raw_geom.area * 111.0 * 88.0) if 120.0 <= raw_geom.centroid.x <= 135.0 else (raw_geom.area / 1000000.0), 0.1)
                    pop_density = matched_pop / area_sq_km
                    
                    if matched_pop > 0: 
                        raw_points.append({'lat': centroid.y, 'lng': centroid.x, 'density': pop_density})
                        
                    features.append({
                        'type': 'Feature', 
                        'properties': {
                            'ADM_NM': geo_name, 
                            'population': int(matched_pop), 
                            'area_km2': round(area_sq_km, 2), 
                            'density': int(pop_density)
                        }, 
                        'geometry': mapping(simple_geom)
                    })
                except Exception as e:
                    continue
                    
            if raw_points:
                density_cutoff = np.percentile([p['density'] for p in raw_points], 50)
                heat_points = [[p['lat'], p['lng'], p['density']] for p in raw_points if p['density'] >= density_cutoff]
            
            simplified_geojson = {'type': 'FeatureCollection', 'features': features}
    except Exception as e:
        print("공간 데이터 로드 오류:", e)
        
    return df, heat_points, simplified_geojson

with st.spinner("빅데이터 연산 및 지도 최적화 중입니다..."):
    stores_df, heat_points, geojson_data = load_and_process_data()

# ==========================================
# 4. 앱 UI 및 사이드바
# ==========================================
st.title("신규 입점 검토 시스템")
st.caption("인구 밀집 히트맵을 참고하여 신규 주소를 검색하고 기존 매장과의 상권을 비교하세요.")

with st.sidebar:
    st.markdown("### ⚙️ 설정")
    user_kakao_key = st.text_input("카카오 REST API 키", value="", type="password")
    st.markdown("---")
    st.markdown("**🔴 신규 입점 검토 반경**")
    radius_km = st.slider("반경 범위 (km)", min_value=0.5, max_value=20.0, value=3.0, step=0.5)
    st.success(f"✅ 연동된 기존 시공점: {len(stores_df)}개")
    if heat_points: st.info("🔥 인구 밀집 상권 히트맵 로드 완료")

def get_kakao_coords(address, api_key):
    headers = {"Authorization": f"KakaoAK {api_key}"}
    for search_type in ['address', 'keyword']:
        res = requests.get(f"https://dapi.kakao.com/v2/local/search/{search_type}.json?query={address}", headers=headers)
        if res.status_code == 200 and res.json()['documents']:
            doc = res.json()['documents'][0]
            return float(doc['y']), float(doc['x']), doc.get('address_name', doc.get('place_name', address))
    return None, None, None

search_col1, search_col2 = st.columns([3, 1])
with search_col1: address = st.text_input("신규 검토 주소 입력", placeholder="예: 성남시 중원구 희망로 415", label_visibility="collapsed")
with search_col2: search_clicked = st.button("입점 상권 검토")

search_lat, search_lng, found_name = None, None, None

if search_clicked:
    if not user_kakao_key: st.error("사이드바에 카카오 API 키를 입력해주세요.")
    elif address.strip():
        with st.spinner("위치 및 상권 데이터 분석 중..."):
            search_lat, search_lng, found_name = get_kakao_coords(address, user_kakao_key)
            if search_lat and search_lng:
                st.success(f"📍 '{found_name}' 위치 탐색 성공")
                c1, c2 = st.columns(2)
                with c1: st.markdown("**위도**"); st.code(f"{search_lat:.6f}", language="text")
                with c2: st.markdown("**경도**"); st.code(f"{search_lng:.6f}", language="text")
            else: st.error("주소를 찾을 수 없습니다.")

# ==========================================
# 5. 지도 생성 및 레이어 병합
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)

center_lat = search_lat if search_lat else (stores_df['lat'].mean() if not stores_df.empty else 37.5665)
center_lng = search_lng if search_lng else (stores_df['lng'].mean() if not stores_df.empty else 126.9780)
zoom_level = 14 if search_lat and radius_km <= 2 else (13 if search_lat and radius_km <= 5 else 11)

m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_level, tiles='OpenStreetMap')

# 히트맵
if heat_points:
    HeatMap(heat_points, name='🔥 주요 인구 밀집 스팟', radius=14, blur=10, min_opacity=0.35,
            gradient={0.3: '#00E676', 0.6: '#FFEB3B', 0.85: '#FF9800', 1.0: '#D50000'}, show=True).add_to(m)

# 행정동 경계
if geojson_data:
    folium.GeoJson(
        geojson_data, name='🗺️ 행정동 경계선 (인구/면적)',
        style_function=lambda f: {'fillColor': 'transparent', 'color': '#777777', 'weight': 0.5, 'fillOpacity': 0.0},
        highlight_function=lambda f: {'color': '#000000', 'weight': 1.8, 'fillOpacity': 0.1},
        tooltip=folium.GeoJsonTooltip(fields=['ADM_NM', 'population', 'density'], aliases=['행정동:', '인구수:', '인구밀도:'], localize=True),
        show=False
    ).add_to(m)

# 커버리지 반경 원
radii = [3, 5, 10, 15]
for r_km in radii:
    is_default = (r_km == 5)
    radius_layer = folium.FeatureGroup(name=f'🎯 기존 시공점 커버리지 ({r_km}km)', show=is_default)
    for _, row in stores_df.iterrows():
        is_active = row['is_active'] == 'Y'
        folium.Circle(
            location=[row['lat'], row['lng']], radius=r_km * 1000,
            color='#0288D1' if is_active else '#9E9E9E', fill=True, 
            fillColor='#B3E5FC' if is_active else '#E0E0E0', fillOpacity=0.1, weight=1
        ).add_to(radius_layer)
    radius_layer.add_to(m)

# 📍 [업체 마커 레이어] - 요청한 4가지 핵심 정보 팝업 카드 적용
shop_layer = folium.FeatureGroup(name=f'📍 전체 매장 마커', show=True)
for _, row in stores_df.iterrows():
    popup_html = f"""
    <div style="font-family:'Pretendard', sans-serif; min-width:190px; padding: 4px;">
        <h4 style="margin:0 0 8px 0; color:#1E3A8A; font-size:14px; font-weight:700; border-bottom:2px solid #38BDF8; padding-bottom:5px;">
            📍 {row['name']}
        </h4>
        <div style="font-size:12px; color:#374151; line-height:1.6;">
            <p style="margin:3px 0;"><b>• 업체코드:</b> <span style="color:#111827;">{row['code']}</span></p>
            <p style="margin:3px 0;"><b>• 업체명:</b> <span style="color:#111827;">{row['name']}</span></p>
            <p style="margin:3px 0;"><b>• 월평균 예약 수:</b> <span style="color:#2563EB; font-weight:600;">{row['avg_monthly_reservations']:,.0f}건</span></p>
            <p style="margin:3px 0;"><b>• 재구매율:</b> <span style="color:#059669; font-weight:600;">{row['repurchase_rate']:.1f}%</span></p>
        </div>
    </div>
    """
    
    folium.Marker(
        location=[row['lat'], row['lng']],
        popup=folium.Popup(popup_html, max_width=260),
        tooltip=f"{row['name']} ({row['code']})",
        icon=folium.DivIcon(
            html=get_clean_pin('#38BDF8', is_search=False),
            icon_size=(12, 18),
            icon_anchor=(6, 18)
        )
    ).add_to(shop_layer)
shop_layer.add_to(m)

# 검색 위치 마커
if search_lat and search_lng:
    search_layer = folium.FeatureGroup(name=f'🚨 신규 입점 검토 위치', show=True)
    folium.Circle(
        location=[search_lat, search_lng], radius=radius_km * 1000,
        color='#DC2626', fill=True, fillColor='#EF4444', fillOpacity=0.2, weight=2.5
    ).add_to(search_layer)

    svg_pin = get_clean_pin('#DC2626', is_search=True)
    folium.Marker(
        location=[search_lat, search_lng], popup=f"<b>신규 검토 위치</b><br>{address}", tooltip=f"검토 반경: {radius_km}km",
        icon=folium.DivIcon(html=svg_pin, icon_size=(20, 28), icon_anchor=(10, 28))
    ).add_to(search_layer)
    search_layer.add_to(m)

folium.LayerControl(collapsed=False, position='topright').add_to(m)

zoom_script = """
<script>
document.addEventListener("DOMContentLoaded", function() { setTimeout(function() {
    var map_keys = Object.keys(window).filter(k => k.startsWith('map_'));
    if (map_keys.length > 0) {
        var myMap = window[map_keys[0]];
        function adjustMarkerScale() {
            var zoom = myMap.getZoom();
            var scale = Math.max(0.4, Math.min(3.0, 1.0 + (zoom - 11) * 0.25));
            document.querySelectorAll('.custom-pin-icon').forEach(p => p.style.transform = 'scale(' + scale + ')');
        }
        myMap.on('zoomend', adjustMarkerScale); adjustMarkerScale();
    }
}, 500);});
</script>
"""
m.get_root().html.add_child(folium.Element(zoom_script))

components.html(m.get_root().render(), height=650)
