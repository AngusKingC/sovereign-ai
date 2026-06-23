"""Evaluation metrics for comparing LLM outputs against gold-standard responses.

This module provides lightweight, self-contained metric functions for offline
evaluation. All metrics use stdlib only (no external dependencies).

Metric priority order for evaluation:
- exact_match: strict ground truth (character-level identity after normalization)
- token_f1: fuzzy ground truth (word overlap, order-independent)
- bleu, cosine_similarity: supplementary metrics with known limitations
"""

from collections import Counter
import math
import re
import string


def compute_exact_match(predicted: str, gold: str) -> float:
    """Return 1.0 if strings match exactly, 0.0 otherwise.
    
    Args:
        predicted: The model's output
        gold: The gold-standard (expected) output
        
    Returns:
        1.0 if strings match exactly (after stripping whitespace and collapsing multiple spaces), 0.0 otherwise
    """
    predicted_norm = re.sub(r'\s+', ' ', predicted.strip())
    gold_norm = re.sub(r'\s+', ' ', gold.strip())
    return 1.0 if predicted_norm == gold_norm else 0.0


def compute_token_f1(predicted: str, gold: str) -> float:
    """Compute F1 score at token level.
    
    Token F1 measures the harmonic mean of precision and recall at the token level.
    
    Args:
        predicted: The model's output
        gold: The gold-standard (expected) output
        
    Returns:
        F1 score in range [0.0, 1.0]
    """
    pred_clean = predicted.lower().translate(str.maketrans('', '', string.punctuation))
    gold_clean = gold.lower().translate(str.maketrans('', '', string.punctuation))
    pred_tokens = set(pred_clean.split())
    gold_tokens = set(gold_clean.split())
    
    if not gold_tokens:
        return 1.0 if not pred_tokens else 0.0
    
    common = len(pred_tokens & gold_tokens)
    if common == 0:
        return 0.0
    
    precision = common / len(pred_tokens) if pred_tokens else 0.0
    recall = common / len(gold_tokens) if gold_tokens else 0.0
    
    if precision + recall == 0:
        return 0.0
    
    return 2 * (precision * recall) / (precision + recall)


def compute_bleu(predicted: str, gold: str, max_n: int = 2) -> float:
    """Compute BLEU score (simplified version, n-grams up to max_n).
    
    BLEU measures n-gram overlap between predicted and gold text.
    This is a simplified implementation that computes unigram + bigram overlap.
    
    Args:
        predicted: The model's output
        gold: The gold-standard (expected) output
        max_n: Maximum n-gram size to consider (default: 2)
        
    Returns:
        BLEU score in range [0.0, 1.0]
    """
    pred_tokens = predicted.lower().split()
    gold_tokens = gold.lower().split()
    
    if not gold_tokens:
        return 1.0 if not pred_tokens else 0.0
    
    # For simplicity, compute unigram + bigram overlap
    score = 0.0
    for n in range(1, min(max_n + 1, len(gold_tokens) + 1)):
        pred_ngrams = [tuple(pred_tokens[i:i+n]) for i in range(len(pred_tokens) - n + 1)]
        gold_ngrams = [tuple(gold_tokens[i:i+n]) for i in range(len(gold_tokens) - n + 1)]
        
        if not gold_ngrams:
            continue
        
        pred_count = Counter(pred_ngrams)
        gold_count = Counter(gold_ngrams)
        
        matches = sum((pred_count & gold_count).values())
        score += matches / len(gold_ngrams)
    
    return score / min(max_n, len(gold_tokens))


def compute_cosine_similarity(predicted: str, gold: str) -> float:
    """
    Compute cosine similarity of word vectors (bag-of-words implementation).
    
    Self-contained, no external dependencies. Uses word frequency vectors
    and standard cosine similarity formula: dot product / (||pred|| * ||gold||)
    
    Args:
        predicted: The model's output
        gold: The gold-standard (expected) output
        
    Returns:
        Cosine similarity score in range [0.0, 1.0]
    """
    pred_tokens = predicted.lower().split()
    gold_tokens = gold.lower().split()
    
    if not pred_tokens or not gold_tokens:
        return 1.0 if (not pred_tokens and not gold_tokens) else 0.0
    
    pred_count = Counter(pred_tokens)
    gold_count = Counter(gold_tokens)
    
    # Cosine similarity = dot product / (||pred|| * ||gold||)
    common_words = set(pred_count.keys()) & set(gold_count.keys())
    dot_product = sum(pred_count[w] * gold_count[w] for w in common_words)
    
    pred_norm = math.sqrt(sum(c ** 2 for c in pred_count.values()))
    gold_norm = math.sqrt(sum(c ** 2 for c in gold_count.values()))
    
    if pred_norm == 0 or gold_norm == 0:
        return 0.0
    
    return dot_product / (pred_norm * gold_norm)
