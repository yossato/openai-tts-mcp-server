"""
キャッシュシステム

Phase 3: パフォーマンス最適化
- LRUキャッシュによる音声データの高速化
- ハッシュベースの効率的なキャッシュ管理
- TTL（Time To Live）による自動期限切れ
- メモリとディスクのハイブリッドキャッシュ
"""

import hashlib
import json
import pickle
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TTSCacheKey:
    """TTSキャッシュのキークラス"""
    
    def __init__(
        self,
        text: str,
        voice: str,
        speed: float,
        response_format: str,
        instructions: Optional[str] = None
    ):
        """
        キャッシュキーを初期化
        
        Args:
            text: 音声テキスト
            voice: 音声タイプ
            speed: 再生速度
            response_format: 出力形式
            instructions: 音声指示
        """
        self.text = text
        self.voice = voice
        self.speed = speed
        self.response_format = response_format
        self.instructions = instructions
    
    def to_hash(self) -> str:
        """キャッシュキーをハッシュ値に変換"""
        # パラメータを正規化してハッシュ化
        key_data = {
            "text": self.text.strip(),
            "voice": self.voice,
            "speed": round(self.speed, 2),  # 浮動小数点の精度を統一
            "response_format": self.response_format,
            "instructions": self.instructions.strip() if self.instructions else None
        }
        
        # JSON文字列にして安定したハッシュを生成
        key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(key_str.encode('utf-8')).hexdigest()
    
    def __str__(self) -> str:
        return f"TTSCacheKey({self.to_hash()[:12]}...)"


class CacheEntry:
    """キャッシュエントリークラス"""
    
    def __init__(self, file_path: str, created_at: float = None):
        """
        キャッシュエントリーを初期化
        
        Args:
            file_path: 音声ファイルのパス
            created_at: 作成時刻（Unix timestamp）
        """
        self.file_path = file_path
        self.created_at = created_at or time.time()
        self.access_count = 0
        self.last_accessed = self.created_at
    
    def touch(self) -> None:
        """アクセス情報を更新"""
        self.access_count += 1
        self.last_accessed = time.time()
    
    def is_expired(self, ttl_seconds: float) -> bool:
        """TTLに基づく期限切れチェック"""
        return (time.time() - self.created_at) > ttl_seconds
    
    def exists(self) -> bool:
        """ファイルが実際に存在するかチェック"""
        return Path(self.file_path).exists()


class TTSCache:
    """TTS音声キャッシュシステム"""
    
    def __init__(
        self,
        max_size: int = 100,
        ttl_hours: int = 24,
        cache_dir: Optional[Path] = None
    ):
        """
        キャッシュシステムを初期化
        
        Args:
            max_size: 最大キャッシュサイズ（エントリー数）
            ttl_hours: キャッシュの生存時間（時間）
            cache_dir: キャッシュディレクトリ
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_hours * 3600
        self.cache_dir = cache_dir or Path.home() / ".cache" / "openai-tts-mcp" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # LRUキャッシュ（メモリ内のメタデータ）
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # キャッシュメタデータファイル
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        
        # 統計情報
        self.hits = 0
        self.misses = 0
        
        # 初期化時にメタデータを読み込み
        self._load_metadata()
        self._cleanup_expired()
    
    def _load_metadata(self) -> None:
        """キャッシュメタデータを読み込み"""
        if not self.metadata_file.exists():
            return
        
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            for key, entry_data in metadata.items():
                entry = CacheEntry(
                    file_path=entry_data["file_path"],
                    created_at=entry_data["created_at"]
                )
                entry.access_count = entry_data.get("access_count", 0)
                entry.last_accessed = entry_data.get("last_accessed", entry.created_at)
                
                # ファイルが実際に存在し、期限切れでない場合のみ復元
                if entry.exists() and not entry.is_expired(self.ttl_seconds):
                    self._cache[key] = entry
            
            logger.info(f"Loaded {len(self._cache)} cache entries from metadata")
            
        except Exception as e:
            logger.warning(f"Failed to load cache metadata: {e}")
            # メタデータファイルが破損している場合は削除
            self.metadata_file.unlink(missing_ok=True)
    
    def _save_metadata(self) -> None:
        """キャッシュメタデータを保存"""
        try:
            metadata = {}
            for key, entry in self._cache.items():
                metadata[key] = {
                    "file_path": entry.file_path,
                    "created_at": entry.created_at,
                    "access_count": entry.access_count,
                    "last_accessed": entry.last_accessed
                }
            
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
        except Exception as e:
            logger.warning(f"Failed to save cache metadata: {e}")
    
    def _cleanup_expired(self) -> None:
        """期限切れエントリーの削除"""
        expired_keys = []
        
        for key, entry in self._cache.items():
            if entry.is_expired(self.ttl_seconds) or not entry.exists():
                expired_keys.append(key)
                # ファイルも削除
                try:
                    Path(entry.file_path).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Failed to delete cached file {entry.file_path}: {e}")
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
            self._save_metadata()
    
    def _evict_lru(self) -> None:
        """LRUエントリーを削除してスペースを確保"""
        if len(self._cache) >= self.max_size:
            # 最も古いエントリーを削除
            key, entry = self._cache.popitem(last=False)
            try:
                Path(entry.file_path).unlink(missing_ok=True)
                logger.debug(f"Evicted LRU cache entry: {key}")
            except Exception as e:
                logger.warning(f"Failed to delete evicted file {entry.file_path}: {e}")
    
    def get(self, cache_key: TTSCacheKey) -> Optional[str]:
        """
        キャッシュから音声ファイルを取得
        
        Args:
            cache_key: キャッシュキー
            
        Returns:
            Optional[str]: キャッシュされた音声ファイルのパス、見つからない場合はNone
        """
        key_hash = cache_key.to_hash()
        
        if key_hash in self._cache:
            entry = self._cache[key_hash]
            
            # 期限切れチェック
            if entry.is_expired(self.ttl_seconds) or not entry.exists():
                del self._cache[key_hash]
                try:
                    Path(entry.file_path).unlink(missing_ok=True)
                except Exception:
                    pass
                self.misses += 1
                return None
            
            # アクセス情報更新（LRUのために末尾に移動）
            entry.touch()
            self._cache.move_to_end(key_hash)
            
            self.hits += 1
            logger.debug(f"Cache hit: {cache_key}")
            return entry.file_path
        
        self.misses += 1
        logger.debug(f"Cache miss: {cache_key}")
        return None
    
    def put(self, cache_key: TTSCacheKey, file_path: str) -> None:
        """
        音声ファイルをキャッシュに保存
        
        Args:
            cache_key: キャッシュキー
            file_path: 音声ファイルのパス
        """
        key_hash = cache_key.to_hash()
        
        # キャッシュディレクトリにファイルをコピー
        try:
            source_path = Path(file_path)
            if not source_path.exists():
                logger.warning(f"Source file does not exist: {file_path}")
                return
            
            # キャッシュファイル名を生成
            file_extension = source_path.suffix
            cache_file_path = self.cache_dir / f"{key_hash}{file_extension}"
            
            # ファイルをコピー
            import shutil
            shutil.copy2(source_path, cache_file_path)
            
            # LRU削除チェック
            self._evict_lru()
            
            # キャッシュエントリーを作成
            entry = CacheEntry(str(cache_file_path))
            self._cache[key_hash] = entry
            
            # メタデータ保存
            self._save_metadata()
            
            logger.debug(f"Cached file: {cache_key} -> {cache_file_path}")
            
        except Exception as e:
            logger.warning(f"Failed to cache file: {e}")
    
    def clear(self) -> None:
        """キャッシュをクリア"""
        # すべてのキャッシュファイルを削除
        for entry in self._cache.values():
            try:
                Path(entry.file_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to delete cached file {entry.file_path}: {e}")
        
        self._cache.clear()
        
        # メタデータファイルも削除
        self.metadata_file.unlink(missing_ok=True)
        
        # 統計情報リセット
        self.hits = 0
        self.misses = 0
        
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """キャッシュ統計情報を取得"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        # キャッシュサイズの計算
        total_size = 0
        for entry in self._cache.values():
            try:
                total_size += Path(entry.file_path).stat().st_size
            except Exception:
                pass
        
        return {
            "entries": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 2),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "ttl_hours": self.ttl_seconds / 3600
        }
    
    def cleanup(self) -> None:
        """手動クリーンアップ"""
        self._cleanup_expired()
    
    def resize(self, new_max_size: int) -> None:
        """キャッシュサイズを変更"""
        self.max_size = new_max_size
        
        # 新しいサイズを超えている場合はLRUで削除
        while len(self._cache) > self.max_size:
            self._evict_lru()
        
        self._save_metadata()
        logger.info(f"Cache resized to {new_max_size} entries")


# グローバルキャッシュインスタンス（シングルトン）
_cache_instance: Optional[TTSCache] = None


def get_cache(
    max_size: int = 100,
    ttl_hours: int = 24,
    cache_dir: Optional[Path] = None
) -> TTSCache:
    """
    キャッシュインスタンスを取得（シングルトン）
    
    Args:
        max_size: 最大キャッシュサイズ
        ttl_hours: キャッシュの生存時間
        cache_dir: キャッシュディレクトリ
        
    Returns:
        TTSCache: キャッシュインスタンス
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = TTSCache(max_size, ttl_hours, cache_dir)
    return _cache_instance


def clear_cache() -> None:
    """グローバルキャッシュをクリア"""
    global _cache_instance
    if _cache_instance:
        _cache_instance.clear()
        _cache_instance = None
