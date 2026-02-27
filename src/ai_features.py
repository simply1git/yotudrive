"""
YotuDrive 2.0 - AI-Powered Features
State-of-the-art artificial intelligence capabilities
"""

import os
import json
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
import cv2
import speech_recognition as sr
from pydub import AudioSegment
import easyocr
import torch
from transformers import pipeline, AutoTokenizer, AutoModel
import faiss
from datetime import datetime, timedelta

class AIContentAnalyzer:
    """Advanced AI-powered content analysis and organization"""
    
    def __init__(self):
        self.ocr_reader = easyocr.Reader(['en', 'es', 'fr', 'de', 'it', 'pt'])
        self.text_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.image_features = {}
        self.text_features = {}
        self.audio_features = {}
        
        # Initialize AI models
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize AI models for content analysis"""
        try:
            # Image classification model
            self.image_classifier = pipeline(
                "image-classification",
                model="google/vit-base-patch16-224"
            )
            
            # Text analysis model
            self.text_analyzer = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest"
            )
            
            # Object detection model
            self.object_detector = pipeline(
                "object-detection",
                model="facebook/detr-resnet-50"
            )
            
            print("✅ AI models initialized successfully")
        except Exception as e:
            print(f"⚠️ AI models initialization failed: {e}")
            self.image_classifier = None
            self.text_analyzer = None
            self.object_detector = None
    
    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """Comprehensive image analysis using AI"""
        try:
            image = Image.open(image_path)
            
            analysis = {
                'basic_info': self._analyze_image_basic(image),
                'objects': self._detect_objects(image_path),
                'text': self._extract_text_from_image(image_path),
                'features': self._extract_image_features(image),
                'similarity': self._calculate_image_similarity(image_path)
            }
            
            return analysis
            
        except Exception as e:
            return {'error': str(e)}
    
    def _analyze_image_basic(self, image: Image.Image) -> Dict[str, Any]:
        """Basic image analysis"""
        return {
            'size': image.size,
            'mode': image.mode,
            'format': image.format,
            'aspect_ratio': image.size[0] / image.size[1],
            'file_size': os.path.getsize(image.filename) if hasattr(image, 'filename') else 0
        }
    
    def _detect_objects(self, image_path: str) -> List[Dict[str, Any]]:
        """Detect objects in image using AI"""
        if not self.object_detector:
            return []
        
        try:
            results = self.object_detector(image_path)
            objects = []
            
            for result in results:
                objects.append({
                    'label': result['label'],
                    'confidence': result['score'],
                    'box': result['box']
                })
            
            return objects
            
        except Exception as e:
            return [{'error': str(e)}]
    
    def _extract_text_from_image(self, image_path: str) -> Dict[str, Any]:
        """Extract text from image using OCR"""
        try:
            results = self.ocr_reader.readtext(image_path)
            
            extracted_text = []
            for (bbox, text, confidence) in results:
                extracted_text.append({
                    'text': text,
                    'confidence': confidence,
                    'bbox': bbox
                })
            
            full_text = ' '.join([item['text'] for item in extracted_text])
            
            return {
                'full_text': full_text,
                'segments': extracted_text,
                'word_count': len(full_text.split())
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _extract_image_features(self, image: Image.Image) -> Dict[str, Any]:
        """Extract visual features from image"""
        try:
            # Convert to numpy array
            img_array = np.array(image)
            
            # Color histogram
            if len(img_array.shape) == 3:
                hist_r = np.histogram(img_array[:, :, 0], bins=256)[0]
                hist_g = np.histogram(img_array[:, :, 1], bins=256)[0]
                hist_b = np.histogram(img_array[:, :, 2], bins=256)[0]
                color_hist = np.concatenate([hist_r, hist_g, hist_b])
            else:
                color_hist = np.histogram(img_array, bins=256)[0]
            
            # Edge detection
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
            edges = cv2.Canny(gray, 100, 200)
            edge_density = np.sum(edges > 0) / edges.size
            
            # Texture analysis
            texture = self._analyze_texture(gray)
            
            return {
                'color_histogram': color_hist.tolist(),
                'edge_density': float(edge_density),
                'texture_features': texture,
                'dominant_colors': self._get_dominant_colors(img_array)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _analyze_texture(self, gray_image: np.ndarray) -> Dict[str, float]:
        """Analyze texture features"""
        try:
            # Calculate Local Binary Pattern
            from skimage.feature import local_binary_pattern
            
            radius = 3
            n_points = 8 * radius
            lbp = local_binary_pattern(gray_image, n_points, radius, method='uniform')
            
            # Calculate texture statistics
            lbp_hist, _ = np.histogram(lbp.ravel(), bins=n_points + 2)
            lbp_hist = lbp_hist.astype(float)
            lbp_hist /= (lbp_hist.sum() + 1e-7)
            
            return {
                'lbp_contrast': float(np.std(lbp_hist)),
                'lbp_energy': float(np.sum(lbp_hist ** 2)),
                'lbp_homogeneity': float(np.sum(lbp_hist / (1 + np.abs(np.arange(len(lbp_hist)) - np.mean(lbp_hist)))))
            }
            
        except Exception:
            return {'lbp_contrast': 0.0, 'lbp_energy': 0.0, 'lbp_homogeneity': 0.0}
    
    def _get_dominant_colors(self, img_array: np.ndarray) -> List[List[int]]:
        """Get dominant colors using K-means clustering"""
        try:
            # Reshape image to be a list of pixels
            pixels = img_array.reshape(-1, 3)
            
            # Apply K-means clustering
            kmeans = KMeans(n_clusters=5, random_state=42)
            kmeans.fit(pixels)
            
            # Get dominant colors
            colors = kmeans.cluster_centers_.astype(int)
            
            return colors.tolist()
            
        except Exception:
            return [[128, 128, 128]]  # Default gray
    
    def _calculate_image_similarity(self, image_path: str) -> Dict[str, Any]:
        """Calculate similarity to other images"""
        try:
            # This would compare with stored image features
            # For now, return placeholder
            return {
                'similar_images': [],
                'similarity_scores': [],
                'duplicate_probability': 0.0
            }
        except Exception as e:
            return {'error': str(e)}
    
    def analyze_document(self, file_path: str) -> Dict[str, Any]:
        """Analyze document content using AI"""
        try:
            # Extract text from document
            text = self._extract_text_from_document(file_path)
            
            if not text:
                return {'error': 'No text could be extracted'}
            
            analysis = {
                'text_content': text,
                'sentiment': self._analyze_sentiment(text),
                'keywords': self._extract_keywords(text),
                'summary': self._generate_summary(text),
                'language': self._detect_language(text),
                'readability': self._analyze_readability(text)
            }
            
            return analysis
            
        except Exception as e:
            return {'error': str(e)}
    
    def _extract_text_from_document(self, file_path: str) -> str:
        """Extract text from various document formats"""
        try:
            ext = Path(file_path).suffix.lower()
            
            if ext == '.pdf':
                return self._extract_from_pdf(file_path)
            elif ext in ['.doc', '.docx']:
                return self._extract_from_word(file_path)
            elif ext in ['.txt', '.md']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                return ''
                
        except Exception:
            return ''
    
    def _extract_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF"""
        try:
            import PyPDF2
            
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ''
                
                for page in reader.pages:
                    text += page.extract_text()
                
                return text
                
        except Exception:
            return ''
    
    def _extract_from_word(self, doc_path: str) -> str:
        """Extract text from Word document"""
        try:
            import docx
            
            doc = docx.Document(doc_path)
            text = ''
            
            for paragraph in doc.paragraphs:
                text += paragraph.text + '\n'
            
            return text
            
        except Exception:
            return ''
    
    def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text"""
        if not self.text_analyzer:
            return {'sentiment': 'neutral', 'confidence': 0.5}
        
        try:
            result = self.text_analyzer(text[:512])  # Limit text length
            return {
                'sentiment': result[0]['label'].lower(),
                'confidence': result[0]['score']
            }
        except Exception:
            return {'sentiment': 'neutral', 'confidence': 0.5}
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        try:
            # Simple keyword extraction using TF-IDF
            vectorizer = TfidfVectorizer(max_features=10, stop_words='english')
            tfidf_matrix = vectorizer.fit_transform([text])
            feature_names = vectorizer.get_feature_names_out()
            tfidf_scores = tfidf_matrix.toarray()[0]
            
            # Get top keywords
            top_indices = tfidf_scores.argsort()[-5:][::-1]
            keywords = [feature_names[i] for i in top_indices]
            
            return keywords
            
        except Exception:
            return []
    
    def _generate_summary(self, text: str) -> str:
        """Generate summary of text"""
        try:
            # Simple extractive summarization
            sentences = text.split('.')
            if len(sentences) <= 3:
                return text
            
            # Score sentences based on length and position
            sentence_scores = []
            for i, sentence in enumerate(sentences):
                if len(sentence.strip()) > 10:
                    score = len(sentence.split()) * (1.0 - i / len(sentences))
                    sentence_scores.append((sentence.strip(), score))
            
            # Get top 3 sentences
            sentence_scores.sort(key=lambda x: x[1], reverse=True)
            summary_sentences = [s[0] for s in sentence_scores[:3]]
            
            return '. '.join(summary_sentences) + '.'
            
        except Exception:
            return text[:200] + '...' if len(text) > 200 else text
    
    def _detect_language(self, text: str) -> str:
        """Detect language of text"""
        try:
            from langdetect import detect
            return detect(text)
        except Exception:
            return 'en'
    
    def _analyze_readability(self, text: str) -> Dict[str, float]:
        """Analyze readability of text"""
        try:
            sentences = text.split('.')
            words = text.split()
            
            avg_sentence_length = len(words) / len(sentences) if sentences else 0
            avg_word_length = sum(len(word) for word in words) / len(words) if words else 0
            
            return {
                'avg_sentence_length': avg_sentence_length,
                'avg_word_length': avg_word_length,
                'total_sentences': len(sentences),
                'total_words': len(words),
                'readability_score': 100 - (1.015 * avg_sentence_length + 84.6 * (avg_word_length / 100))
            }
        except Exception:
            return {'readability_score': 50.0}
    
    def analyze_audio(self, audio_path: str) -> Dict[str, Any]:
        """Analyze audio content using AI"""
        try:
            analysis = {
                'transcription': self._transcribe_audio(audio_path),
                'audio_features': self._extract_audio_features(audio_path),
                'speech_analysis': self._analyze_speech(audio_path)
            }
            
            return analysis
            
        except Exception as e:
            return {'error': str(e)}
    
    def _transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """Transcribe audio to text"""
        try:
            recognizer = sr.Recognizer()
            
            # Convert audio to WAV format if needed
            if not audio_path.endswith('.wav'):
                audio = AudioSegment.from_file(audio_path)
                wav_path = audio_path.rsplit('.', 1)[0] + '.wav'
                audio.export(wav_path, format='wav')
                audio_path = wav_path
            
            with sr.AudioFile(audio_path) as source:
                audio_data = recognizer.record(source)
            
            # Try Google Speech Recognition first
            try:
                text = recognizer.recognize_google(audio_data)
                return {'text': text, 'confidence': 0.9, 'method': 'google'}
            except:
                # Fallback to Sphinx
                text = recognizer.recognize_sphinx(audio_data)
                return {'text': text, 'confidence': 0.7, 'method': 'sphinx'}
                
        except Exception as e:
            return {'error': str(e)}
    
    def _extract_audio_features(self, audio_path: str) -> Dict[str, Any]:
        """Extract audio features"""
        try:
            audio = AudioSegment.from_file(audio_path)
            
            # Basic features
            duration = len(audio) / 1000.0  # Convert to seconds
            channels = audio.channels
            frame_rate = audio.frame_rate
            sample_width = audio.sample_width
            
            # Calculate volume statistics
            volume = audio.dBFS
            max_volume = audio.max_dBFS
            
            return {
                'duration_seconds': duration,
                'channels': channels,
                'frame_rate': frame_rate,
                'sample_width': sample_width,
                'volume_dbfs': volume,
                'max_volume_dbfs': max_volume,
                'is_stereo': channels == 2
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _analyze_speech(self, audio_path: str) -> Dict[str, Any]:
        """Analyze speech patterns"""
        try:
            # This would include more advanced speech analysis
            # For now, return basic analysis
            transcription = self._transcribe_audio(audio_path)
            
            if 'text' in transcription:
                text = transcription['text']
                words = text.split()
                
                return {
                    'word_count': len(words),
                    'estimated_speaking_rate': len(words) / 60,  # words per minute
                    'has_speech': len(words) > 0,
                    'language': self._detect_language(text)
                }
            else:
                return {'has_speech': False}
                
        except Exception as e:
            return {'error': str(e)}

class SmartOrganizer:
    """AI-powered file organization and recommendations"""
    
    def __init__(self):
        self.ai_analyzer = AIContentAnalyzer()
        self.file_clusters = {}
        self.user_patterns = {}
        self.recommendations = []
    
    def organize_files_automatically(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """Automatically organize files into smart folders"""
        organized_files = {
            'Documents': [],
            'Images': [],
            'Videos': [],
            'Audio': [],
            'Archives': [],
            'Code': [],
            'Other': []
        }
        
        for file_path in file_paths:
            category = self._categorize_file(file_path)
            organized_files[category].append(file_path)
        
        return organized_files
    
    def _categorize_file(self, file_path: str) -> str:
        """Categorize file based on content and metadata"""
        ext = Path(file_path).suffix.lower()
        
        # Basic extension-based categorization
        if ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf']:
            return 'Documents'
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
            return 'Images'
        elif ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']:
            return 'Videos'
        elif ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg']:
            return 'Audio'
        elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            return 'Archives'
        elif ext in ['.py', '.js', '.html', '.css', '.java', '.cpp']:
            return 'Code'
        else:
            return 'Other'
    
    def find_similar_files(self, target_file: str, file_list: List[str]) -> List[Dict[str, Any]]:
        """Find files similar to target file"""
        similar_files = []
        
        for file_path in file_list:
            if file_path == target_file:
                continue
            
            similarity_score = self._calculate_file_similarity(target_file, file_path)
            
            if similarity_score > 0.7:  # High similarity threshold
                similar_files.append({
                    'file_path': file_path,
                    'similarity': similarity_score,
                    'similarity_type': self._get_similarity_type(target_file, file_path)
                })
        
        # Sort by similarity
        similar_files.sort(key=lambda x: x['similarity'], reverse=True)
        
        return similar_files[:10]  # Return top 10 similar files
    
    def _calculate_file_similarity(self, file1: str, file2: str) -> float:
        """Calculate similarity between two files"""
        try:
            # For now, use filename similarity
            name1 = Path(file1).stem.lower()
            name2 = Path(file2).stem.lower()
            
            # Simple string similarity
            common_chars = set(name1) & set(name2)
            total_chars = set(name1) | set(name2)
            
            if len(total_chars) == 0:
                return 0.0
            
            return len(common_chars) / len(total_chars)
            
        except Exception:
            return 0.0
    
    def _get_similarity_type(self, file1: str, file2: str) -> str:
        """Determine type of similarity"""
        ext1 = Path(file1).suffix.lower()
        ext2 = Path(file2).suffix.lower()
        
        if ext1 != ext2:
            return 'different_type'
        
        if ext1 in ['.jpg', '.jpeg', '.png', '.gif']:
            return 'visual'
        elif ext1 in ['.mp3', '.wav', '.flac']:
            return 'audio'
        elif ext1 in ['.mp4', '.avi', '.mkv']:
            return 'video'
        elif ext1 in ['.pdf', '.doc', '.docx', '.txt']:
            return 'content'
        else:
            return 'filename'
    
    def generate_smart_recommendations(self, user_files: List[str]) -> List[Dict[str, Any]]:
        """Generate AI-powered recommendations"""
        recommendations = []
        
        # Recommendation 1: Duplicate files
        duplicates = self._find_potential_duplicates(user_files)
        if duplicates:
            recommendations.append({
                'type': 'duplicate_files',
                'title': 'Potential Duplicate Files Found',
                'description': f'Found {len(duplicates)} groups of potentially duplicate files',
                'action': 'review_duplicates',
                'files': duplicates
            })
        
        # Recommendation 2: Large files
        large_files = self._find_large_files(user_files)
        if large_files:
            recommendations.append({
                'type': 'large_files',
                'title': 'Large Files Detected',
                'description': f'Found {len(large_files)} files larger than 100MB',
                'action': 'optimize_storage',
                'files': large_files
            })
        
        # Recommendation 3: Old files
        old_files = self._find_old_files(user_files)
        if old_files:
            recommendations.append({
                'type': 'old_files',
                'title': 'Old Files for Review',
                'description': f'Found {len(old_files)} files not accessed in over 6 months',
                'action': 'archive_or_delete',
                'files': old_files
            })
        
        return recommendations
    
    def _find_potential_duplicates(self, file_list: List[str]) -> List[List[str]]:
        """Find potential duplicate files"""
        duplicates = []
        processed = set()
        
        for file_path in file_list:
            if file_path in processed:
                continue
            
            similar_files = self.find_similar_files(file_path, file_list)
            if similar_files:
                duplicate_group = [file_path] + [f['file_path'] for f in similar_files]
                duplicates.append(duplicate_group)
                processed.update(duplicate_group)
        
        return duplicates
    
    def _find_large_files(self, file_list: List[str]) -> List[Dict[str, Any]]:
        """Find files larger than 100MB"""
        large_files = []
        
        for file_path in file_list:
            try:
                size = os.path.getsize(file_path)
                if size > 100 * 1024 * 1024:  # 100MB
                    large_files.append({
                        'file_path': file_path,
                        'size': size,
                        'size_human': f"{size / (1024*1024):.1f} MB"
                    })
            except Exception:
                continue
        
        return sorted(large_files, key=lambda x: x['size'], reverse=True)
    
    def _find_old_files(self, file_list: List[str]) -> List[Dict[str, Any]]:
        """Find files not accessed in over 6 months"""
        old_files = []
        six_months_ago = time.time() - (6 * 30 * 24 * 60 * 60)
        
        for file_path in file_list:
            try:
                access_time = os.path.getatime(file_path)
                if access_time < six_months_ago:
                    old_files.append({
                        'file_path': file_path,
                        'last_access': datetime.fromtimestamp(access_time).strftime('%Y-%m-%d'),
                        'days_old': int((time.time() - access_time) / (24 * 60 * 60))
                    })
            except Exception:
                continue
        
        return sorted(old_files, key=lambda x: x['days_old'], reverse=True)

class PersonalizedSearch:
    """AI-powered personalized search and recommendations"""
    
    def __init__(self):
        self.search_history = []
        self.user_preferences = {}
        self.search_index = {}
        self.embedding_model = None
        
        # Initialize embedding model
        self._initialize_embeddings()
    
    def _initialize_embeddings(self):
        """Initialize text embedding model"""
        try:
            # This would initialize a proper embedding model
            # For now, use TF-IDF as placeholder
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.embedding_model = TfidfVectorizer(max_features=1000)
            print("✅ Search embeddings initialized")
        except Exception as e:
            print(f"⚠️ Search embeddings initialization failed: {e}")
    
    def intelligent_search(self, query: str, file_list: List[str], user_context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Intelligent search with AI-powered ranking"""
        results = []
        
        # Analyze query intent
        query_analysis = self._analyze_query_intent(query)
        
        # Search files
        for file_path in file_list:
            score = self._calculate_relevance_score(file_path, query, query_analysis, user_context)
            
            if score > 0.1:  # Minimum relevance threshold
                results.append({
                    'file_path': file_path,
                    'relevance_score': score,
                    'match_type': self._get_match_type(file_path, query),
                    'preview': self._generate_preview(file_path, query)
                })
        
        # Sort by relevance
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Apply personalization
        if user_context:
            results = self._apply_personalization(results, user_context)
        
        return results[:20]  # Return top 20 results
    
    def _analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """Analyze user query intent"""
        query_lower = query.lower()
        
        intent = {
            'type': 'general',
            'file_types': [],
            'time_range': None,
            'sentiment': None,
            'keywords': query.split()
        }
        
        # Detect file type preferences
        file_type_keywords = {
            'image': ['image', 'photo', 'picture', 'jpg', 'png', 'gif'],
            'document': ['document', 'pdf', 'doc', 'text', 'file'],
            'video': ['video', 'movie', 'mp4', 'avi', 'clip'],
            'audio': ['audio', 'music', 'song', 'mp3', 'wav']
        }
        
        for file_type, keywords in file_type_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                intent['file_types'].append(file_type)
        
        # Detect time preferences
        if any(word in query_lower for word in ['recent', 'new', 'latest']):
            intent['time_range'] = 'recent'
        elif any(word in query_lower for word in ['old', 'previous', 'earlier']):
            intent['time_range'] = 'old'
        
        return intent
    
    def _calculate_relevance_score(self, file_path: str, query: str, query_analysis: Dict[str, Any], user_context: Dict[str, Any] = None) -> float:
        """Calculate relevance score for file"""
        score = 0.0
        
        try:
            filename = Path(file_path).name.lower()
            query_lower = query.lower()
            
            # Filename matching (highest weight)
            if query_lower in filename:
                score += 0.8
            
            # Partial filename matching
            for word in query.split():
                if word.lower() in filename:
                    score += 0.4
            
            # File type preference
            if query_analysis['file_types']:
                file_category = self._get_file_category(file_path)
                if file_category in query_analysis['file_types']:
                    score += 0.3
            
            # Time preference
            if query_analysis['time_range']:
                file_time = os.path.getmtime(file_path)
                current_time = time.time()
                
                if query_analysis['time_range'] == 'recent':
                    days_old = (current_time - file_time) / (24 * 60 * 60)
                    if days_old < 30:
                        score += 0.2
                elif query_analysis['time_range'] == 'old':
                    days_old = (current_time - file_time) / (24 * 60 * 60)
                    if days_old > 180:
                        score += 0.2
            
            # User context boost
            if user_context:
                score += self._calculate_context_boost(file_path, user_context)
            
        except Exception:
            pass
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _get_file_category(self, file_path: str) -> str:
        """Get file category"""
        ext = Path(file_path).suffix.lower()
        
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            return 'image'
        elif ext in ['.pdf', '.doc', '.docx', '.txt']:
            return 'document'
        elif ext in ['.mp4', '.avi', '.mkv', '.mov']:
            return 'video'
        elif ext in ['.mp3', '.wav', '.flac', '.aac']:
            return 'audio'
        else:
            return 'other'
    
    def _calculate_context_boost(self, file_path: str, user_context: Dict[str, Any]) -> float:
        """Calculate context-based relevance boost"""
        boost = 0.0
        
        # Frequently accessed files
        if 'frequent_files' in user_context:
            if file_path in user_context['frequent_files']:
                boost += 0.1
        
        # User preferences
        if 'preferred_types' in user_context:
            file_category = self._get_file_category(file_path)
            if file_category in user_context['preferred_types']:
                boost += 0.1
        
        # Recent searches
        if 'recent_searches' in user_context:
            for recent_search in user_context['recent_searches']:
                if any(word in Path(file_path).name.lower() for word in recent_search.split()):
                    boost += 0.05
        
        return boost
    
    def _get_match_type(self, file_path: str, query: str) -> str:
        """Determine type of match"""
        filename = Path(file_path).name.lower()
        query_lower = query.lower()
        
        if query_lower in filename:
            return 'exact_match'
        elif any(word.lower() in filename for word in query.split()):
            return 'partial_match'
        else:
            return 'context_match'
    
    def _generate_preview(self, file_path: str, query: str) -> str:
        """Generate preview for search result"""
        try:
            filename = Path(file_path).name
            
            # Highlight matching parts
            highlighted = filename
            for word in query.split():
                if word.lower() in filename.lower():
                    highlighted = highlighted.replace(word, f"**{word}**")
            
            return highlighted
            
        except Exception:
            return Path(file_path).name
    
    def _apply_personalization(self, results: List[Dict[str, Any]], user_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply personalization to search results"""
        if not user_context:
            return results
        
        # Re-rank based on user behavior
        for result in results:
            # Boost frequently accessed files
            if 'frequent_files' in user_context:
                if result['file_path'] in user_context['frequent_files']:
                    result['relevance_score'] *= 1.2
            
            # Boost preferred file types
            if 'preferred_types' in user_context:
                file_category = self._get_file_category(result['file_path'])
                if file_category in user_context['preferred_types']:
                    result['relevance_score'] *= 1.1
        
        # Re-sort after personalization
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return results

# Global AI features instance
ai_features = AIContentAnalyzer()
smart_organizer = SmartOrganizer()
personalized_search = PersonalizedSearch()
