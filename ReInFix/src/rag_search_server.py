import os

from flask import Flask, request, jsonify
import pandas as pd
import ast
import openai
from functools import lru_cache
from openai import OpenAI
from scipy.spatial.distance import cosine

from src.config import OPENAI_API_KEY

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
app = Flask(__name__)

client = OpenAI()


@lru_cache(maxsize=None)
def load_data(file_path):
    df = pd.read_csv(file_path)
    print("Loading data...")

    def safe_eval(x):
        try:
            return ast.literal_eval(x)
        except:
            return None

    df['ada_embedding'] = df['ada_embedding'].apply(safe_eval)
    print("Loading completed")
    df = df.dropna(subset=['ada_embedding'])
    return df


def get_embedding(text, model="text-embedding-3-large"):
    # text = text.replace("\n", " ")
    return client.embeddings.create(input=[text], model=model).data[0].embedding


def search_reviews(df, input_pattern, n, threshold):
    input_embedding = get_embedding(input_pattern, model="text-embedding-3-large")
    df["similarity"] = df.ada_embedding.apply(lambda x: 1 - cosine(x, input_embedding))
    filtered_df = df[df["similarity"] > threshold]

    if filtered_df.empty:
        return pd.DataFrame()

    results = (
        filtered_df.sort_values("similarity", ascending=False)
        .head(n)
    )

    return results


datafile_path = "../retrieval_base/embedded_cause_97k.csv"
df = load_data(datafile_path)
print("Data loaded successfully.")


@app.route('/search', methods=['POST'])
def search():
    data = request.json
    query = data.get('query')
    n = data.get('n')
    threshold = data.get('threshold')

    if not query:
        return jsonify({"error": "No query provided"}), 400

    results = search_reviews(df, query, n=n, threshold=threshold)

    response = []
    if results.empty:
        response.append({"message": "No examples with similarity greater than the threshold"})
    else:
        for _, row in results.iterrows():
            response.append({
                "similarity": float(row['similarity']),
                "buggy_code": row['BuggyCode'],
                "fixed_code": row['FixedCode'],
                "root_cause": row['RootCause']
            })

    return jsonify(response)


if __name__ == '__main__':
    app.run(debug=False, use_reloader=False)