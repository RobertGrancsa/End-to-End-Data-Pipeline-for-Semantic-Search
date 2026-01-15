"""
Streamlit Frontend for Semantic Search

A simple web interface for querying the semantic search pipeline.

Author: Robert Grancsa
"""

import streamlit as st
import time
import sys
import os
from typing import List, Dict

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Page configuration
st.set_page_config(
    page_title="Semantic Search Engine",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .search-result {
        padding: 15px;
        margin: 10px 0;
        border-radius: 8px;
        background-color: #f0f2f6;
        border-left: 4px solid #1f77b4;
    }
    .result-title {
        font-size: 1.1em;
        font-weight: bold;
        color: #1f77b4;
    }
    .result-score {
        float: right;
        color: #666;
    }
    .result-text {
        margin-top: 10px;
        color: #333;
    }
    .result-url {
        font-size: 0.9em;
        color: #888;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_pipeline():
    """Initialize and cache the pipeline"""
    from src.pipeline.data_pipeline import DataPipeline
    
    pipeline = DataPipeline(use_kafka=False)
    pipeline.initialize_components(['processing', 'opensearch'])
    return pipeline


def render_result(result: Dict, rank: int):
    """Render a single search result"""
    st.markdown(f"""
    <div class="search-result">
        <span class="result-score">Score: {result['score']:.4f}</span>
        <div class="result-title">{rank}. {result.get('title', 'Untitled')[:80]}</div>
        <div class="result-url">
            <a href="{result.get('url', '#')}" target="_blank">{result.get('url', '')}</a>
        </div>
        <div class="result-text">{result['text'][:300]}...</div>
    </div>
    """, unsafe_allow_html=True)


def main():
    # Header
    st.title("🔍 Semantic Search Engine")
    st.markdown("""
    Search through indexed documents using semantic (vector) search, 
    traditional text search, or hybrid search combining both approaches.
    """)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Search Settings")
        
        search_type = st.selectbox(
            "Search Type",
            options=["hybrid", "semantic", "text"],
            format_func=lambda x: {
                "hybrid": "🔄 Hybrid (Recommended)",
                "semantic": "🧠 Semantic (Vector)",
                "text": "📝 Text (BM25)"
            }.get(x, x)
        )
        
        num_results = st.slider(
            "Number of Results",
            min_value=1,
            max_value=50,
            value=10
        )
        
        st.markdown("---")
        
        st.header("📊 Index Info")
        try:
            pipeline = get_pipeline()
            doc_count = pipeline.os_client.count_documents()
            st.metric("Documents Indexed", doc_count)
            
            health = pipeline.os_client.get_cluster_health()
            status = health.get('status', 'unknown')
            status_color = {
                'green': '🟢',
                'yellow': '🟡',
                'red': '🔴'
            }.get(status, '⚪')
            st.write(f"Cluster Status: {status_color} {status}")
        except Exception as e:
            st.error(f"Could not connect to OpenSearch: {e}")
        
        st.markdown("---")
        
        st.header("ℹ️ About")
        st.markdown("""
        This search engine uses:
        - **Semantic Search**: all-MiniLM-L6-v2 embeddings
        - **Vector Database**: OpenSearch with k-NN
        - **Hybrid Ranking**: Combines BM25 + vector similarity
        """)
    
    # Main search interface
    col1, col2 = st.columns([4, 1])
    
    with col1:
        query = st.text_input(
            "Enter your search query",
            placeholder="e.g., What is machine learning?",
            label_visibility="collapsed"
        )
    
    with col2:
        search_button = st.button("🔍 Search", type="primary", use_container_width=True)
    
    # Perform search
    if search_button and query:
        try:
            pipeline = get_pipeline()
            
            with st.spinner("Searching..."):
                start_time = time.time()
                results = pipeline.search(
                    query=query,
                    k=num_results,
                    search_type=search_type
                )
                search_time = time.time() - start_time
            
            # Display results
            if results:
                st.success(f"Found {len(results)} results in {search_time:.3f} seconds")
                
                for i, result in enumerate(results, 1):
                    render_result(result, i)
            else:
                st.warning("No results found. Try a different query.")
                
        except Exception as e:
            st.error(f"Search failed: {e}")
    
    # Example queries
    if not query:
        st.markdown("---")
        st.subheader("💡 Example Queries")
        
        examples = [
            "What is machine learning?",
            "How do neural networks work?",
            "Explain natural language processing",
            "Deep learning applications",
            "Vector embeddings for search"
        ]
        
        cols = st.columns(len(examples))
        for col, example in zip(cols, examples):
            with col:
                if st.button(example, key=f"example_{example}"):
                    st.session_state['query'] = example
                    st.rerun()


# Index management section
def admin_section():
    """Admin section for index management"""
    st.header("🛠️ Admin Tools")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Refresh Index"):
            try:
                pipeline = get_pipeline()
                pipeline.index_manager.refresh_index(pipeline.index_name)
                st.success("Index refreshed!")
            except Exception as e:
                st.error(f"Failed: {e}")
    
    with col2:
        if st.button("📊 Get Index Stats"):
            try:
                pipeline = get_pipeline()
                info = pipeline.index_manager.get_index_info(pipeline.index_name)
                st.json(info)
            except Exception as e:
                st.error(f"Failed: {e}")
    
    with col3:
        if st.button("⚠️ Recreate Index", type="secondary"):
            if st.checkbox("I understand this will delete all data"):
                try:
                    pipeline = get_pipeline()
                    pipeline.index_manager.recreate_index(pipeline.index_name)
                    st.success("Index recreated!")
                except Exception as e:
                    st.error(f"Failed: {e}")


if __name__ == "__main__":
    main()
    
    # Show admin section in expander
    with st.expander("🔧 Admin Tools"):
        admin_section()
