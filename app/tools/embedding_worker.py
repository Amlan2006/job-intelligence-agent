import json
import sys

from fastembed import TextEmbedding

if __name__ == "__main__":
    texts = json.loads(sys.stdin.read())
    model = TextEmbedding(model_name=sys.argv[1], cache_dir=sys.argv[2], threads=2)
    vectors = list(model.embed(texts))
    print(json.dumps({text: vector.tolist() for text, vector in zip(texts, vectors, strict=True)}))
