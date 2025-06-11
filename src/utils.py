"""
ユーティリティ関数

Phase 3: 高度な機能サポート
- 長文の自動分割（4096文字制限対応）
- 文章の自然な区切りでの分割
- 音声ファイルの結合・管理
- テキスト前処理
"""

import re
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class TextSplitter:
    """テキスト分割クラス"""
    
    # 文章の区切り文字（優先度順）
    SENTENCE_ENDINGS = [
        '。', '！', '？',  # 日本語の文末
        '.', '!', '?',     # 英語の文末
        '：', ':',         # コロン
        '；', ';',         # セミコロン
    ]
    
    # 段落の区切り
    PARAGRAPH_SEPARATORS = [
        '\n\n',   # 空行
        '\r\n\r\n',  # Windows形式の空行
    ]
    
    def __init__(self, max_length: int = 4000):
        """
        テキスト分割器を初期化
        
        Args:
            max_length: 分割する最大文字数（OpenAI APIの4096文字制限に対応）
        """
        self.max_length = max_length
    
    def split_text(self, text: str) -> List[str]:
        """
        テキストを自然な区切りで分割
        
        Args:
            text: 分割対象のテキスト
            
        Returns:
            List[str]: 分割されたテキストのリスト
        """
        text = text.strip()
        
        if len(text) <= self.max_length:
            return [text]
        
        logger.info(f"Splitting long text: {len(text)} characters")
        
        chunks = []
        remaining_text = text
        
        while remaining_text:
            if len(remaining_text) <= self.max_length:
                chunks.append(remaining_text)
                break
            
            # 適切な分割点を見つける
            split_point = self._find_split_point(remaining_text)
            
            if split_point == -1:
                # 自然な分割点が見つからない場合は強制分割
                split_point = self.max_length
                logger.warning(f"Forced text split at {split_point} characters")
            
            chunk = remaining_text[:split_point].strip()
            if chunk:
                chunks.append(chunk)
            
            remaining_text = remaining_text[split_point:].strip()
        
        logger.info(f"Text split into {len(chunks)} chunks")
        return chunks
    
    def _find_split_point(self, text: str) -> int:
        """
        自然な分割点を見つける
        
        Args:
            text: 検索対象のテキスト
            
        Returns:
            int: 分割点の位置、見つからない場合は-1
        """
        # 最大長を超えない範囲で検索
        search_range = min(len(text), self.max_length)
        search_text = text[:search_range]
        
        # 1. 段落区切りを優先
        for separator in self.PARAGRAPH_SEPARATORS:
            pos = search_text.rfind(separator)
            if pos > self.max_length * 0.5:  # 分割点が長さの半分以上の位置
                return pos + len(separator)
        
        # 2. 文末記号で分割
        best_pos = -1
        for ending in self.SENTENCE_ENDINGS:
            pos = search_text.rfind(ending)
            if pos > self.max_length * 0.3:  # 分割点が長さの30%以上の位置
                if pos > best_pos:
                    best_pos = pos + len(ending)
        
        if best_pos > -1:
            return best_pos
        
        # 3. 改行で分割
        pos = search_text.rfind('\n')
        if pos > self.max_length * 0.3:
            return pos + 1
        
        # 4. 単語境界で分割（スペースやカンマ）
        for delimiter in [', ', '、', ' ']:
            pos = search_text.rfind(delimiter)
            if pos > self.max_length * 0.5:
                return pos + len(delimiter)
        
        return -1


class AudioFileMerger:
    """音声ファイル結合クラス"""
    
    def __init__(self):
        """音声ファイル結合器を初期化"""
        pass
    
    def merge_audio_files(
        self,
        file_paths: List[str],
        output_format: str = "mp3",
        output_dir: Optional[Path] = None
    ) -> str:
        """
        複数の音声ファイルを結合
        
        Args:
            file_paths: 結合する音声ファイルのパスリスト
            output_format: 出力形式
            output_dir: 出力ディレクトリ
            
        Returns:
            str: 結合された音声ファイルのパス
            
        Raises:
            Exception: ファイル結合に失敗した場合
        """
        if not file_paths:
            raise ValueError("結合するファイルが指定されていません")
        
        if len(file_paths) == 1:
            return file_paths[0]
        
        try:
            # pydubを使用して音声ファイルを結合
            from pydub import AudioSegment
            
            logger.info(f"Merging {len(file_paths)} audio files")
            
            # 最初のファイルを読み込み
            combined = AudioSegment.from_file(file_paths[0])
            
            # 他のファイルを順次結合
            for file_path in file_paths[1:]:
                audio = AudioSegment.from_file(file_path)
                combined += audio
            
            # 出力ファイル名を生成
            output_dir = output_dir or Path(tempfile.gettempdir()) / "openai_tts_mcp"
            output_dir.mkdir(exist_ok=True)
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_path = output_dir / f"merged_{timestamp}.{output_format}"
            
            # ファイルを出力
            combined.export(str(output_path), format=output_format)
            
            logger.info(f"Audio files merged: {output_path}")
            return str(output_path)
            
        except ImportError:
            # pydubが利用できない場合は簡易結合
            logger.warning("pydub not available, using simple concatenation")
            return self._simple_concatenate(file_paths, output_format, output_dir)
        
        except Exception as e:
            logger.error(f"Failed to merge audio files: {e}")
            raise Exception(f"音声ファイルの結合に失敗しました: {str(e)}") from e
    
    def _simple_concatenate(
        self,
        file_paths: List[str],
        output_format: str,
        output_dir: Optional[Path]
    ) -> str:
        """
        シンプルなファイル連結（バイナリ結合）
        
        注意: これは正式な音声結合ではなく、緊急用のフォールバック
        """
        output_dir = output_dir or Path(tempfile.gettempdir()) / "openai_tts_mcp"
        output_dir.mkdir(exist_ok=True)
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = output_dir / f"concatenated_{timestamp}.{output_format}"
        
        with open(output_path, 'wb') as output_file:
            for file_path in file_paths:
                with open(file_path, 'rb') as input_file:
                    output_file.write(input_file.read())
        
        logger.warning(f"Files concatenated (not properly merged): {output_path}")
        return str(output_path)


class TextProcessor:
    """テキスト前処理クラス"""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """
        テキストの正規化
        
        Args:
            text: 正規化対象のテキスト
            
        Returns:
            str: 正規化されたテキスト
        """
        if not text:
            return ""
        
        # 空白文字の正規化
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 連続する句読点の正規化
        text = re.sub(r'[。]{2,}', '。', text)
        text = re.sub(r'[！]{2,}', '！', text)
        text = re.sub(r'[？]{2,}', '？', text)
        text = re.sub(r'[.]{2,}', '.', text)
        text = re.sub(r'[!]{2,}', '!', text)
        text = re.sub(r'[?]{2,}', '?', text)
        
        return text
    
    @staticmethod
    def extract_speech_text(text: str) -> str:
        """
        音声合成に適したテキストを抽出
        
        Args:
            text: 元のテキスト
            
        Returns:
            str: 音声合成用に最適化されたテキスト
        """
        # URLの除去
        text = re.sub(r'https?://[^\s]+', '', text)
        
        # メールアドレスの除去
        text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', text)
        
        # HTMLタグの除去
        text = re.sub(r'<[^>]+>', '', text)
        
        # マークダウン記法の簡素化
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # 太字
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # 斜体
        text = re.sub(r'`(.*?)`', r'\1', text)        # コード
        
        # 余分な記号の除去
        text = re.sub(r'[#*_`~\[\]{}]', '', text)
        
        return TextProcessor.normalize_text(text)
    
    @staticmethod
    def estimate_speech_duration(text: str, speed: float = 1.0) -> float:
        """
        音声の推定再生時間を計算
        
        Args:
            text: 音声テキスト
            speed: 再生速度
            
        Returns:
            float: 推定再生時間（秒）
        """
        # 日本語: 約400文字/分、英語: 約150単語/分
        japanese_chars = len(re.sub(r'[a-zA-Z\s]', '', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        
        # 推定時間（分）
        japanese_minutes = japanese_chars / 400
        english_minutes = english_words / 150
        
        total_minutes = japanese_minutes + english_minutes
        total_seconds = total_minutes * 60
        
        # 速度調整
        adjusted_seconds = total_seconds / speed
        
        return max(adjusted_seconds, 1.0)  # 最低1秒


def split_long_text(text: str, max_length: int = 4000) -> List[str]:
    """
    長いテキストを分割（便利関数）
    
    Args:
        text: 分割対象のテキスト
        max_length: 最大文字数
        
    Returns:
        List[str]: 分割されたテキストのリスト
    """
    splitter = TextSplitter(max_length)
    return splitter.split_text(text)


def merge_audio_files(
    file_paths: List[str],
    output_format: str = "mp3",
    output_dir: Optional[Path] = None
) -> str:
    """
    音声ファイルを結合（便利関数）
    
    Args:
        file_paths: 結合する音声ファイルのパスリスト
        output_format: 出力形式
        output_dir: 出力ディレクトリ
        
    Returns:
        str: 結合された音声ファイルのパス
    """
    merger = AudioFileMerger()
    return merger.merge_audio_files(file_paths, output_format, output_dir)


def normalize_text_for_speech(text: str) -> str:
    """
    音声合成用にテキストを正規化（便利関数）
    
    Args:
        text: 正規化対象のテキスト
        
    Returns:
        str: 正規化されたテキスト
    """
    processor = TextProcessor()
    return processor.extract_speech_text(text)


def estimate_speech_duration(text: str, speed: float = 1.0) -> float:
    """
    音声の推定再生時間を計算（便利関数）
    
    Args:
        text: 音声テキスト
        speed: 再生速度
        
    Returns:
        float: 推定再生時間（秒）
    """
    processor = TextProcessor()
    return processor.estimate_speech_duration(text, speed)
