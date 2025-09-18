import os
import boto3
import json
import time
import statistics
import pandas as pd
from botocore.config import Config
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# 네이버 클라우드 Object Storage 설정
SERVICE_NAME = "s3"
ENDPOINT_URL = "https://kr.object.ncloudstorage.com"
REGION_NAME = "kr-standard"
ACCESS_KEY = os.getenv("NCP_IAM_ACCESS_KEY")
SECRET_KEY = os.getenv("NCP_IAM_SECRET_KEY")
BUCKET_NAME = "rapa-maiu-sfacspace"

# boto3 클라이언트 생성
s3 = boto3.client(
    SERVICE_NAME,
    endpoint_url=ENDPOINT_URL,
    region_name=REGION_NAME,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=Config(s3={"addressing_style": "path"}),
)

# 설정
PROCESSED_FOLDERS_FILE = "processed_folders.json"
OUTPUT_DIR = "stats_output"
CHECK_INTERVAL = 300  # 5분마다 체크 (초 단위)

class VideoStatsProcessor:
    def __init__(self):
        self.processed_folders = self.load_processed_folders()
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
    
    def load_processed_folders(self):
        """처리된 폴더 목록을 로드"""
        if os.path.exists(PROCESSED_FOLDERS_FILE):
            with open(PROCESSED_FOLDERS_FILE, 'r') as f:
                return set(json.load(f))
        return set()
    
    def save_processed_folders(self):
        """처리된 폴더 목록을 저장"""
        with open(PROCESSED_FOLDERS_FILE, 'w') as f:
            json.dump(list(self.processed_folders), f, indent=2)
    
    def get_all_upload_folders(self):
        """'raw/uploads/' 내의 모든 폴더 목록을 가져오기"""
        prefix_base = 'raw/uploads/'
        folders = []
        
        continuation_token = None
        while True:
            params = {
                'Bucket': BUCKET_NAME,
                'Prefix': prefix_base,
                'Delimiter': '/'
            }
            if continuation_token:
                params['ContinuationToken'] = continuation_token
            
            response = s3.list_objects_v2(**params)
            
            if 'CommonPrefixes' in response:
                batch_folders = [content['Prefix'] for content in response['CommonPrefixes']]
                folders.extend(batch_folders)
            
            if response.get('IsTruncated', False):
                continuation_token = response.get('NextContinuationToken')
            else:
                break
        
        return folders
    
    def parse_duration(self, duration_str):
        """duration 문자열 -> 초 변환 함수"""
        try:
            t = datetime.strptime(duration_str, "%H:%M:%S")
            delta = timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
            return int(delta.total_seconds())
        except Exception as e:
            print(f"Invalid duration format: {duration_str} - {e}")
            return 0
    
    def seconds_to_hms(self, seconds):
        """초를 시:분:초 형태로 변환하는 함수"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}"
    
    def get_json_files_from_folder(self, folder_prefix):
        """특정 폴더에서 모든 JSON 파일 목록을 가져오기 (페이지네이션 처리)"""
        manifests_prefix = f"{folder_prefix}manifests/"
        json_files = []
        
        continuation_token = None
        total_objects = 0
        
        while True:
            params = {
                'Bucket': BUCKET_NAME,
                'Prefix': manifests_prefix
            }
            if continuation_token:
                params['ContinuationToken'] = continuation_token
            
            response = s3.list_objects_v2(**params)
            
            if 'Contents' in response:
                batch_files = [item['Key'] for item in response['Contents'] if item['Key'].endswith('.json')]
                json_files.extend(batch_files)
                total_objects += len(response['Contents'])
            
            if response.get('IsTruncated', False):
                continuation_token = response.get('NextContinuationToken')
            else:
                break
        
        return json_files
    
    def process_folder(self, folder_prefix):
        """특정 폴더의 영상 길이 통계를 처리"""
        folder_name = folder_prefix.strip('/').split('/')[-1]
        print(f"\n{'='*60}")
        print(f"폴더 처리 시작: {folder_name}")
        print(f"{'='*60}")
        
        # JSON 파일 목록 가져오기
        json_files = self.get_json_files_from_folder(folder_prefix)
        print(f"JSON 파일 발견: {len(json_files)}개")
        
        if not json_files:
            print(f"폴더 {folder_name}에서 JSON 파일을 찾을 수 없습니다.")
            return False
        
        # 각 영상의 길이를 저장할 리스트
        durations_seconds = []
        print(f"JSON 파일 읽는 중... (총 {len(json_files)}개 파일)")
        
        for i, key in enumerate(json_files, 1):
            try:
                obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
                content = obj['Body'].read().decode('utf-8')
                data = json.loads(content)
                
                duration_str = data.get('duration', None)
                if duration_str:
                    duration_seconds = self.parse_duration(duration_str)
                    if duration_seconds > 0:
                        durations_seconds.append(duration_seconds)
                
                # 진행상황 표시
                if i % 100 == 0 or i == len(json_files):
                    print(f"진행중... {i}/{len(json_files)} 파일 처리 완료")
                    
            except Exception as e:
                print(f"파일 처리 중 오류 발생 ({key}): {e}")
        
        if not durations_seconds:
            print(f"폴더 {folder_name}에서 유효한 영상 길이 데이터를 찾을 수 없습니다.")
            return False
        
        # 통계 계산
        total_videos = len(durations_seconds)
        total_duration_seconds = sum(durations_seconds)
        average_duration_seconds = total_duration_seconds / total_videos
        min_duration_seconds = min(durations_seconds)
        max_duration_seconds = max(durations_seconds)
        median_duration_seconds = statistics.median(durations_seconds)
        
        # 길이별 분포 계산
        ranges = [(0, 1800), (1800, 2400), (2400, 3000), (3000, 3600), (3600, float('inf'))]
        range_labels = ["30분 미만", "30-39분", "40-49분", "50-59분", "1시간 이상"]
        
        distribution = {}
        for (min_sec, max_sec), label in zip(ranges, range_labels):
            count = len([d for d in durations_seconds if min_sec <= d < max_sec])
            percentage = (count / total_videos) * 100
            distribution[f"{label}_개수"] = count
            distribution[f"{label}_비율"] = round(percentage, 1)
        
        # 통계 데이터를 CSV로 저장
        stats_data = {
            "폴더명": [folder_name],
            "처리시간": [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            "총_영상_개수": [total_videos],
            "총_영상_시간_초": [total_duration_seconds],
            "총_영상_시간_HMS": [self.seconds_to_hms(total_duration_seconds)],
            "평균_길이_초": [round(average_duration_seconds, 2)],
            "평균_길이_HMS": [self.seconds_to_hms(average_duration_seconds)],
            "최소_길이_초": [min_duration_seconds],
            "최소_길이_HMS": [self.seconds_to_hms(min_duration_seconds)],
            "최대_길이_초": [max_duration_seconds],
            "최대_길이_HMS": [self.seconds_to_hms(max_duration_seconds)],
            "중간값_초": [median_duration_seconds],
            "중간값_HMS": [self.seconds_to_hms(median_duration_seconds)]
        }
        
        # 분포 데이터 추가
        for key, value in distribution.items():
            stats_data[key] = [value]
        
        # DataFrame 생성 및 CSV 저장
        stats_df = pd.DataFrame(stats_data)
        csv_path = os.path.join(OUTPUT_DIR, f"video_stats_{folder_name}.csv")
        stats_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        # 개별 영상 길이 데이터도 별도 CSV로 저장 (필요시)
        durations_df = pd.DataFrame(durations_seconds, columns=["duration_sec"])
        durations_csv_path = os.path.join(OUTPUT_DIR, f"video_durations_raw_{folder_name}.csv")
        durations_df.to_csv(durations_csv_path, index=False)
        
        # 결과 출력
        print(f"\n영상 길이 통계 분석 결과 - {folder_name}")
        print("="*50)
        print(f"총 영상 개수: {total_videos}개")
        print(f"총 영상 시간: {self.seconds_to_hms(total_duration_seconds)}")
        print(f"평균 길이: {self.seconds_to_hms(average_duration_seconds)}")
        print(f"최소 길이: {self.seconds_to_hms(min_duration_seconds)}")
        print(f"최대 길이: {self.seconds_to_hms(max_duration_seconds)}")
        print(f"중간값: {self.seconds_to_hms(median_duration_seconds)}")
        print("="*50)
        
        # 길이별 분포 출력
        print(f"\n길이 분포:")
        for (min_sec, max_sec), label in zip(ranges, range_labels):
            count = len([d for d in durations_seconds if min_sec <= d < max_sec])
            percentage = (count / total_videos) * 100
            print(f"{label}: {count}개 ({percentage:.1f}%)")
        
        print(f"\n결과 저장 완료:")
        print(f"- 통계 CSV: {csv_path}")
        print(f"- 원본 데이터 CSV: {durations_csv_path}")
        
        return True
    
    def run_initial_processing(self):
        """초기 실행 시 모든 폴더를 처리"""
        print("초기 실행: 모든 폴더 처리를 시작합니다...")
        
        all_folders = self.get_all_upload_folders()
        print(f"총 {len(all_folders)}개의 폴더를 발견했습니다.")
        
        for i, folder in enumerate(all_folders, 1):
            folder_name = folder.strip('/').split('/')[-1]
            print(f"\n[{i}/{len(all_folders)}] 폴더 처리: {folder_name}")
            
            if self.process_folder(folder):
                self.processed_folders.add(folder)
        
        self.save_processed_folders()
        print(f"\n초기 처리 완료! {len(self.processed_folders)}개 폴더 처리됨")
    
    def check_new_folders(self):
        """새로운 폴더가 있는지 확인하고 처리"""
        current_folders = set(self.get_all_upload_folders())
        new_folders = current_folders - self.processed_folders
        
        if new_folders:
            print(f"\n새로운 폴더 {len(new_folders)}개 발견!")
            for folder in sorted(new_folders):
                folder_name = folder.strip('/').split('/')[-1]
                print(f"새 폴더 처리: {folder_name}")
                
                if self.process_folder(folder):
                    self.processed_folders.add(folder)
            
            self.save_processed_folders()
            print(f"새 폴더 처리 완료!")
        else:
            print("새로운 폴더가 없습니다.")
    
    def run_monitoring(self):
        """지속적으로 새 폴더를 모니터링"""
        print(f"\n모니터링 시작... {CHECK_INTERVAL}초마다 새 폴더 확인")
        
        while True:
            try:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 새 폴더 확인 중...")
                self.check_new_folders()
                
                print(f"{CHECK_INTERVAL}초 후 다시 확인합니다...")
                time.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                print("\n모니터링을 종료합니다.")
                break
            except Exception as e:
                print(f"모니터링 중 오류 발생: {e}")
                print("5초 후 다시 시도합니다...")
                time.sleep(5)

def main():
    processor = VideoStatsProcessor()
    
    # 처리된 폴더가 없으면 초기 실행
    if not processor.processed_folders:
        processor.run_initial_processing()
    else:
        print(f"기존에 처리된 폴더: {len(processor.processed_folders)}개")
    
    # 모니터링 시작
    processor.run_monitoring()

if __name__ == "__main__":
    main()