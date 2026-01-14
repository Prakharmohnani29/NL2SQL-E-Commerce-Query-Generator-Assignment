import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple

class VectorDBManager:
    """
    Manages few-shot examples in a FAISS vector database.
    Retrieves relevant examples based on semantic similarity.
    """
    
    def __init__(self, examples_path: str = "nl2sql/few_shot_examples.json"):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.examples = []
        self.index = None
        self.dimension = 384  # Embedding dimension for all-MiniLM-L6-v2
        
        # Load examples
        with open(examples_path, 'r') as f:
            self.examples = json.load(f)
        
        # Build FAISS index
        self._build_index()
    
    def _build_index(self):
        """Build FAISS index from examples"""
        questions = [ex['question'] for ex in self.examples]
        embeddings = self.model.encode(questions)
        
        # Create FAISS index
        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(embeddings.astype('float32'))
        
        print(f"✓ Vector DB initialized with {len(self.examples)} examples")
    
    def retrieve_similar(self, query: str, k: int = 5) -> List[Dict]:
        """
        Retrieve top-k similar examples for a given query
        
        Args:
            query: Natural language question
            k: Number of examples to retrieve
            
        Returns:
            List of similar examples with scores
        """
        query_embedding = self.model.encode([query])
        distances, indices = self.index.search(
            query_embedding.astype('float32'), 
            min(k, len(self.examples))
        )
        
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            example = self.examples[idx].copy()
            example['similarity_score'] = float(1 / (1 + dist))  # Convert distance to similarity
            results.append(example)
        
        return results
    
    def format_examples_for_prompt(self, examples: List[Dict]) -> str:
        """Format retrieved examples for inclusion in prompt"""
        formatted = []
        for i, ex in enumerate(examples, 1):
            formatted.append(
                f"Example {i}:\n"
                f"Question: {ex['question']}\n"
                f"SQL: {ex['sql']}\n"
            )
        return "\n".join(formatted)

# Example usage
if __name__ == "__main__":
    db = VectorDBManager()
    query = "What are the best selling products?"
    similar = db.retrieve_similar(query, k=3)
    print(f"\nQuery: {query}\n")
    print("Similar examples:")
    for ex in similar:
        print(f"- {ex['question']} (score: {ex['similarity_score']:.3f})")