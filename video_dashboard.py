import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import glob
from pathlib import Path

# Set page config
st.set_page_config(page_title="Video Length Statistics Dashboard", layout="wide")

st.title("📊 Video Length Statistics Dashboard")

@st.cache_data
def load_csv_files():
    """Load all CSV files from stats_output directory"""
    try:
        # Get the current directory
        current_dir = Path(__file__).parent if '__file__' in globals() else Path.cwd()
        stats_dir = current_dir / "stats_output"
        
        # Find all CSV files that contain statistics (not raw data)
        csv_files = glob.glob(str(stats_dir / "video_stats_*.csv"))
        
        if not csv_files:
            return None, f"No CSV files found in {stats_dir}"
        
        dfs = []
        loaded_files = []
        
        for file_path in csv_files:
            try:
                # Try different encodings
                for encoding in ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        dfs.append(df)
                        loaded_files.append(Path(file_path).name)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    st.warning(f"Could not read file: {Path(file_path).name}")
                    
            except Exception as e:
                st.warning(f"Error loading {Path(file_path).name}: {str(e)}")
        
        if not dfs:
            return None, "No files could be loaded successfully"
            
        # Combine all dataframes
        full_df = pd.concat(dfs, ignore_index=True)
        
        return full_df, loaded_files
        
    except Exception as e:
        return None, f"Error accessing stats_output directory: {str(e)}"

# Load data
with st.spinner("Loading CSV files from stats_output directory..."):
    data, message = load_csv_files()

if data is not None:
    st.success(f"✅ Successfully loaded {len(message)} files: {', '.join(message)}")
    
    # Convert numeric columns
    numeric_cols = [
        '총_영상_개수', '총_영상_시간_초', '평균_길이_초', '최소_길이_초', '최대_길이_초', '중간값_초',
        '30분 미만_개수', '30분 미만_비율',
        '30-39분_개수', '30-39분_비율',
        '40-49분_개수', '40-49분_비율',
        '50-59분_개수', '50-59분_비율',
        '1시간 이상_개수', '1시간 이상_비율'
    ]
    
    # Only convert columns that exist in the dataframe
    existing_numeric_cols = [col for col in numeric_cols if col in data.columns]
    if existing_numeric_cols:
        data[existing_numeric_cols] = data[existing_numeric_cols].apply(pd.to_numeric, errors='coerce')

    st.subheader("📄 Full Data Preview")
    st.dataframe(data)

    st.markdown("---")

    ## KPI Display
    st.subheader("📌 Key Performance Indicators")

    if '총_영상_개수' in data.columns:
        total_videos = int(data['총_영상_개수'].sum())
        avg_length = data['평균_길이_초'].mean() if '평균_길이_초' in data.columns else 0
        max_length = data['최대_길이_초'].max() if '최대_길이_초' in data.columns else 0
        min_length = data['최소_길이_초'].min() if '최소_길이_초' in data.columns else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Videos", f"{total_videos:,}")
        col2.metric("Average Length (min)", f"{avg_length/60:.2f}")
        col3.metric("Max Length (min)", f"{max_length/60:.2f}")
        col4.metric("Min Length (min)", f"{min_length/60:.2f}")
    else:
        st.warning("Required columns for KPI calculation not found")

    st.markdown("---")

    ## Video Length Category Visualization
    st.subheader("🎯 Video Length Distribution by Categories")

    dist_cols = {
        "Under 30 min": "30분 미만_개수",
        "30-39 min": "30-39분_개수",
        "40-49 min": "40-49분_개수",
        "50-59 min": "50-59분_개수",
        "Over 60 min": "1시간 이상_개수"
    }

    # Check if distribution columns exist
    available_dist_cols = {k: v for k, v in dist_cols.items() if v in data.columns}
    
    if available_dist_cols:
        dist_df = data[list(available_dist_cols.values())].sum().reset_index()
        dist_df.columns = ['Category', 'Count']
        dist_df['Category'] = dist_df['Category'].map({v: k for k, v in available_dist_cols.items()})

        fig, ax = plt.subplots(figsize=(10, 4))
        sns.barplot(data=dist_df, x='Category', y='Count', ax=ax, palette='Blues_d')
        ax.set_title("Video Length Distribution")
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)
    else:
        st.warning("Distribution columns not found in the data")

    st.markdown("---")

    # Selection Filter
    st.subheader("🔎 Filter Data by Folder")

    if '폴더명' in data.columns:
        folder_options = data['폴더명'].unique().tolist()
        selected_folders = st.multiselect("Select Folders", folder_options, default=folder_options)

        filtered_df = data[data['폴더명'].isin(selected_folders)]
        st.dataframe(filtered_df)

        # Download Button
        st.download_button(
            label="📥 Download Filtered Data (CSV)",
            data=filtered_df.to_csv(index=False).encode('utf-8-sig'),
            file_name='filtered_video_stats.csv',
            mime='text/csv'
        )
    else:
        st.warning("Folder name column not found")
        st.dataframe(data)
        
        # Download Button for all data
        st.download_button(
            label="📥 Download All Data (CSV)",
            data=data.to_csv(index=False).encode('utf-8-sig'),
            file_name='all_video_stats.csv',
            mime='text/csv'
        )

    # Show column information for debugging
    with st.expander("🔍 Data Information"):
        st.write("**Available Columns:**")
        st.write(data.columns.tolist())
        st.write(f"**Data Shape:** {data.shape}")
        
else:
    st.error(f"❌ {message}")
    
    # Manual file upload as fallback
    st.subheader("📂 Manual File Upload (Fallback)")
    st.info("You can manually upload CSV files as a fallback option.")
    
    uploaded_files = st.file_uploader("Upload CSV files", type=["csv"], accept_multiple_files=True)
    
    if uploaded_files:
        dfs = []
        for file in uploaded_files:
            try:
                df = pd.read_csv(file, encoding='utf-8-sig')
            except UnicodeDecodeError:
                df = pd.read_csv(file, encoding='cp949')
            dfs.append(df)

        manual_df = pd.concat(dfs, ignore_index=True)
        st.success("✅ Files uploaded successfully!")
        st.dataframe(manual_df)

# Instructions for deployment
st.sidebar.markdown("""
## 📋 Deployment Instructions

1. **Repository Structure:**
   ```
   streamlit/
   ├── app.py (this file)
   ├── requirements.txt
   └── stats_output/
       ├── video_stats_folder1.csv
       ├── video_stats_folder2.csv
       └── ...
   ```

2. **Deploy on Streamlit Cloud:**
   - Push to GitHub
   - Connect at share.streamlit.io
   - Select repository: streamlit
   - Main file: app.py

3. **Auto-refresh data:**
   - Update CSV files in stats_output/
   - Push to GitHub
   - App will auto-reload
""")

st.sidebar.markdown("---")
st.sidebar.markdown("**Last updated:** Auto-refresh from GitHub")
