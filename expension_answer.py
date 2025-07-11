from helper_utils import project_embeddings, word_wrap
from pypdf import PdfReader
import os
from openai import OpenAI
from dotenv import load_dotenv
import umap

load_dotenv()

openai_key = os.getenv("OPEN_API_KEY")
openai_client = OpenAI(api_key=openai_key)

reader = PdfReader("./microsoft-annual-report.pdf")
pdf_texts = [p.extract_text().strip() for p in reader.pages]

#filter the empty strings
pdf_texts = [text for text in pdf_texts if text]

# print(word_wrap(pdf_texts[0], width=100))

from langchain.text_splitter import (RecursiveCharacterTextSplitter, SentenceTransformersTokenTextSplitter)

character_splitter = RecursiveCharacterTextSplitter(
    separators = ["\n\n", "\n", ".", " ", ""], chunk_size=1000, chunk_overlap=200
)

character_split_text = character_splitter.split_text("\n\n".join(pdf_texts[0]))

# print(word_wrap(character_split_text[10]))
# print("Number of chunks:", len(character_split_text))

token_splitter = SentenceTransformersTokenTextSplitter(tokens_per_chunk=256, chunk_overlap=0)

token_split_texts = []
for text in character_split_text:
    token_split_texts += token_splitter.split_text(text)

# print(word_wrap(token_split_texts[10]))
# print("Number of chunks:", len(token_split_texts))

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

embedding_function= SentenceTransformerEmbeddingFunction()

chroma_client = chromadb.Client()

chroma_collection = chroma_client.create_collection(name="microsoft-annual-report", embedding_function=embedding_function)

ids = [str(i) for i in range(len(token_split_texts))]

chroma_collection.add(
    ids= ids, documents= token_split_texts
)

chroma_collection.count()

query = "What is the revenue of Microsoft in 2022?"

results = chroma_collection.query(
    query_texts=[query], n_results=2)

retrieved_texts = results['documents'][0]

# for document in retrieved_texts:
#     print(word_wrap(document))
#     print("\n" + "="*100 + "\n")


def augment_query_generated(query, model="gpt-3.5-turbo"):
    prompt = """You are a helpful expert financial research assistant. 
   Provide an example answer to the given question, that might be found in a document like an annual report."""
    messages = [
        {
            "role": "system",
            "content": prompt,
        },
        {"role": "user", "content": query},
    ]

    response = openai_client.chat.completions.create(
        model=model,
        messages=messages,
    )
    content = response.choices[0].message.content
    return content

original_query = "What was the total profit for the year, and how does it compare to the previous year?"
hypothetical_answer = augment_query_generated(original_query)

joint_query = f"{original_query} {hypothetical_answer}"

results = chroma_collection.query(
    query_texts=joint_query, n_results=3, include=["documents", "embeddings"]
)
retrieved_documents = results["documents"][0]

embeddings = chroma_collection.get(include=["embeddings"])["embeddings"]
umap_transform = umap.UMAP(random_state=0, transform_seed=0).fit(embeddings)
projected_dataset_embeddings = project_embeddings(embeddings, umap_transform)


retrieved_embeddings = results["embeddings"][0]
original_query_embedding = embedding_function([original_query])
augmented_query_embedding = embedding_function([joint_query])

projected_original_query_embedding = project_embeddings(
    original_query_embedding, umap_transform
)
projected_augmented_query_embedding = project_embeddings(
    augmented_query_embedding, umap_transform
)
projected_retrieved_embeddings = project_embeddings(
    retrieved_embeddings, umap_transform
)

import matplotlib.pyplot as plt

# Plot the projected query and retrieved documents in the embedding space
plt.figure()

plt.scatter(
    projected_dataset_embeddings[:, 0],
    projected_dataset_embeddings[:, 1],
    s=10,
    color="gray",
)
plt.scatter(
    projected_retrieved_embeddings[:, 0],
    projected_retrieved_embeddings[:, 1],
    s=100,
    facecolors="none",
    edgecolors="g",
)
plt.scatter(
    projected_original_query_embedding[:, 0],
    projected_original_query_embedding[:, 1],
    s=150,
    marker="X",
    color="r",
)
plt.scatter(
    projected_augmented_query_embedding[:, 0],
    projected_augmented_query_embedding[:, 1],
    s=150,
    marker="X",
    color="orange",
)

plt.gca().set_aspect("equal", "datalim")
plt.title(f"{original_query}")
plt.axis("off")
plt.show()