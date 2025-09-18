import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ✅ 한글 폰트 설정 (NanumGothic)
font_path = "C:/Windows/Fonts/malgun.ttf"  # 윈도우 기본 한글 폰트
font_prop = fm.FontProperties(fname=font_path)
plt.rcParams['font.family'] = font_prop.get_name()
plt.rcParams['axes.unicode_minus'] = False


st.set_page_config(page_title="영상 길이 통계 대시보드", layout="wide")

st.title("📊 영상 길이 통계 대시보드")

# 파일 업로드
uploaded_files = st.file_uploader("📂 CSV 파일 업로드 (여러 파일 가능)", type=["csv"], accept_multiple_files=True)

if uploaded_files:
    dfs = []
    for file in uploaded_files:
        # ✅ 1차 시도: utf-8-sig로 읽기
        try:
            df = pd.read_csv(file, encoding='utf-8-sig')
        except UnicodeDecodeError:
            # ✅ 2차 시도: cp949로 읽기
            df = pd.read_csv(file, encoding='cp949')
        dfs.append(df)

    # 전체 데이터 병합
    full_df = pd.concat(dfs, ignore_index=True)

    # 숫자형 컬럼 자동 변환
    numeric_cols = [
        '총_영상_개수', '총_영상_시간_초', '평균_길이_초', '최소_길이_초', '최대_길이_초', '중간값_초',
        '30분 미만_개수', '30분 미만_비율',
        '30-39분_개수', '30-39분_비율',
        '40-49분_개수', '40-49분_비율',
        '50-59분_개수', '50-59분_비율',
        '1시간 이상_개수', '1시간 이상_비율'
    ]
    full_df[numeric_cols] = full_df[numeric_cols].apply(pd.to_numeric, errors='coerce')

    st.subheader("📄 전체 데이터 미리보기")
    st.dataframe(full_df)

    st.markdown("---")

    ## KPI 표시
    st.subheader("📌 핵심 통계 지표")

    total_videos = int(full_df['총_영상_개수'].sum())
    avg_length = full_df['평균_길이_초'].mean()
    max_length = full_df['최대_길이_초'].max()
    min_length = full_df['최소_길이_초'].min()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 영상 개수", f"{total_videos:,}")
    col2.metric("평균 영상 길이 (초)", f"{avg_length:.2f}")
    col3.metric("최대 길이 (초)", f"{max_length:.2f}")
    col4.metric("최소 길이 (초)", f"{min_length:.2f}")

    st.markdown("---")

    ## 영상 길이 카테고리별 시각화
    st.subheader("🎯 영상 길이 구간별 분포")

    dist_cols = {
        "30분 미만": "30분 미만_개수",
        "30-39분": "30-39분_개수",
        "40-49분": "40-49분_개수",
        "50-59분": "50-59분_개수",
        "1시간 이상": "1시간 이상_개수"
    }

    dist_df = full_df[list(dist_cols.values())].sum().reset_index()
    dist_df.columns = ['구간', '개수']
    dist_df['구간'] = dist_df['구간'].replace(dist_cols)

    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(data=dist_df, x='구간', y='개수', ax=ax, palette='Blues_d')
    ax.set_title("영상 길이 분포")
    st.pyplot(fig)

    st.markdown("---")

    # 선택 필터
    st.subheader("🔎 폴더별 데이터 필터링")

    folder_options = full_df['폴더명'].unique().tolist()
    selected_folders = st.multiselect("폴더 선택", folder_options, default=folder_options)

    filtered_df = full_df[full_df['폴더명'].isin(selected_folders)]

    st.dataframe(filtered_df)

    # 다운로드 버튼
    st.download_button(
        label="📥 필터링된 데이터 다운로드 (CSV)",
        data=filtered_df.to_csv(index=False).encode('utf-8-sig'),
        file_name='filtered_video_stats.csv',
        mime='text/csv'
    )

else:
    st.info("왼쪽 사이드바 또는 위 영역에서 CSV 파일을 업로드해주세요.")
