from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.tools import Tool
from langchain_core.memory import ConversationBufferMemory
from typing import Dict, List, Optional
from nl2sql.vector_db import VectorDBManager
import os
import re

class NL2SQLGenerator:
    """
    Generate SQL queries from natural language using LangChain agents
    with RAG-style prompting and dynamic schema injection.
    """
    
    def __init__(self, model_name: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        # Initialize Ollama LLM
        self.llm = Ollama(
            model=model_name,
            base_url=base_url,
            temperature=0.1,  # Low temperature for consistent SQL generation
        )
        
        # Initialize vector DB for few-shot retrieval
        self.vector_db = VectorDBManager()
        
        # Database schema information
        self.schema = self._load_schema()
        
        # Create two different prompt strategies
        self.detailed_chain = self._create_detailed_chain()
        self.concise_chain = self._create_concise_chain()
        
        # Agent with tools
        self.agent = self._create_sql_agent()
        
        print(f"✓ NL2SQL Generator initialized with model: {model_name}")
    
    def _load_schema(self) -> Dict:
        """Load database schema information"""
        return {
            "customers": {
                "columns": ["customer_id", "customer_name", "email", "country", "city", 
                           "registration_date", "customer_segment"],
                "primary_key": "customer_id",
                "description": "Customer information and demographics"
            },
            "categories": {
                "columns": ["category_id", "category_name", "parent_category_id", "description"],
                "primary_key": "category_id",
                "description": "Product categories with hierarchical structure"
            },
            "products": {
                "columns": ["product_id", "product_name", "category_id", "price", "cost",
                           "stock_quantity", "brand", "rating", "created_date"],
                "primary_key": "product_id",
                "foreign_keys": ["category_id -> categories"],
                "description": "Product catalog with pricing and inventory"
            },
            "orders": {
                "columns": ["order_id", "customer_id", "order_date", "status", "total_amount",
                           "shipping_address", "payment_method"],
                "primary_key": "order_id",
                "foreign_keys": ["customer_id -> customers"],
                "description": "Customer orders and transaction details"
            },
            "order_items": {
                "columns": ["order_item_id", "order_id", "product_id", "quantity", 
                           "unit_price", "discount_percent", "subtotal"],
                "primary_key": "order_item_id",
                "foreign_keys": ["order_id -> orders", "product_id -> products"],
                "description": "Line items for each order"
            },
            "reviews": {
                "columns": ["review_id", "product_id", "customer_id", "rating", 
                           "review_text", "review_date", "helpful_count"],
                "primary_key": "review_id",
                "foreign_keys": ["product_id -> products", "customer_id -> customers"],
                "description": "Customer product reviews and ratings"
            },
            "shipping": {
                "columns": ["shipping_id", "order_id", "shipping_method", "shipping_cost",
                           "shipped_date", "delivery_date", "tracking_number"],
                "primary_key": "shipping_id",
                "foreign_keys": ["order_id -> orders"],
                "description": "Shipping and delivery information"
            },
            "promotions": {
                "columns": ["promotion_id", "promotion_name", "discount_type", 
                           "discount_value", "start_date", "end_date", "category_id"],
                "primary_key": "promotion_id",
                "foreign_keys": ["category_id -> categories"],
                "description": "Marketing promotions and discounts"
            }
        }
    
    def _format_schema(self, relevant_tables: Optional[List[str]] = None) -> str:
        """Format schema information for prompt injection"""
        tables_to_include = relevant_tables or self.schema.keys()
        
        schema_text = "DATABASE SCHEMA:\n\n"
        for table in tables_to_include:
            if table in self.schema:
                info = self.schema[table]
                schema_text += f"Table: {table}\n"
                schema_text += f"Description: {info['description']}\n"
                schema_text += f"Columns: {', '.join(info['columns'])}\n"
                if 'foreign_keys' in info:
                    schema_text += f"Foreign Keys: {', '.join(info['foreign_keys'])}\n"
                schema_text += "\n"
        
        return schema_text
    
    def _create_detailed_chain(self) -> LLMChain:
        """Strategy 1: Detailed prompt with comprehensive instructions"""
        
        # Example prompt template for few-shot learning
        example_template = """
Question: {question}
SQL: {sql}
"""
        
        example_prompt = PromptTemplate(
            input_variables=["question", "sql"],
            template=example_template
        )
        
        # Main prompt template
        prefix = """You are an expert SQL query generator for an e-commerce database.

{schema}

INSTRUCTIONS:
1. Generate a valid PostgreSQL query based on the user's question
2. Use proper JOIN clauses when accessing multiple tables
3. Include appropriate WHERE, GROUP BY, and ORDER BY clauses
4. Use aggregate functions (SUM, AVG, COUNT) when needed
5. Return ONLY the SQL query without any explanation or markdown
6. Do NOT use DROP, DELETE, UPDATE, or TRUNCATE
7. Always use table aliases for clarity
8. Consider NULL values in your logic
9. Use proper date functions for temporal queries
10. Ensure query is syntactically correct

Here are some similar examples for reference:

"""
        
        suffix = """
Now generate the SQL query for this question:

Question: {question}

SQL Query (return ONLY the SQL, no explanation):"""
        
        # This will be populated dynamically with retrieved examples
        prompt = PromptTemplate(
            input_variables=["schema", "question"],
            template=prefix + suffix
        )
        
        return LLMChain(llm=self.llm, prompt=prompt)
    
    def _create_concise_chain(self) -> LLMChain:
        """Strategy 2: Concise prompt with minimal instructions"""
        
        template = """Generate PostgreSQL query. Return only SQL, no explanation.

Tables: customers, products, orders, order_items, categories, reviews, shipping, promotions

Examples:
{examples}

Question: {question}
SQL:"""
        
        prompt = PromptTemplate(
            input_variables=["examples", "question"],
            template=template
        )
        
        return LLMChain(llm=self.llm, prompt=prompt)
    
    def _create_sql_agent(self) -> AgentExecutor:
        """Create LangChain agent with SQL generation tools"""
        
        # Define tools for the agent
        def get_schema_info(table_name: str) -> str:
            """Get schema information for a specific table"""
            if table_name in self.schema:
                return str(self.schema[table_name])
            return f"Table {table_name} not found"
        
        def get_similar_queries(question: str) -> str:
            """Get similar SQL queries from vector database"""
            similar = self.vector_db.retrieve_similar(question, k=3)
            return self.vector_db.format_examples_for_prompt(similar)
        
        tools = [
            Tool(
                name="GetSchemaInfo",
                func=get_schema_info,
                description="Get detailed schema information for a specific table. Input should be a table name."
            ),
            Tool(
                name="GetSimilarQueries",
                func=get_similar_queries,
                description="Get similar SQL query examples from the knowledge base. Input should be the natural language question."
            )
        ]
        
        # Agent prompt template
        agent_template = """You are a SQL expert. Generate SQL queries for an e-commerce database.

Available tools:
{tools}

Use the following format:
Question: the input question
Thought: think about what to do
Action: the action to take (use tools if needed)
Action Input: the input to the action
Observation: the result of the action
... (repeat Thought/Action/Observation as needed)
Thought: I now have enough information to generate the SQL
Final Answer: the SQL query (ONLY SQL, no explanation)

Question: {input}
{agent_scratchpad}"""
        
        prompt = PromptTemplate(
            template=agent_template,
            input_variables=["input", "tools", "agent_scratchpad"]
        )
        
        # Note: For newer LangChain versions, use appropriate agent creation
        # This is a simplified version
        return None  # Agent creation varies by LangChain version
    
    def generate_sql(self, question: str, strategy: str = "detailed") -> str:
        """
        Generate SQL query from natural language question
        
        Args:
            question: Natural language question
            strategy: "detailed" or "concise" prompt strategy
            
        Returns:
            Generated SQL query
        """
        if strategy == "detailed":
            return self._generate_with_detailed_chain(question)
        elif strategy == "concise":
            return self._generate_with_concise_chain(question)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
    
    def _generate_with_detailed_chain(self, question: str) -> str:
        """Generate SQL using detailed strategy"""
        # Retrieve similar examples
        similar_examples = self.vector_db.retrieve_similar(question, k=5)
        examples_text = self.vector_db.format_examples_for_prompt(similar_examples)
        
        # Format schema
        schema_text = self._format_schema()
        
        # Combine into final prompt
        full_prompt = f"""{schema_text}

SIMILAR EXAMPLES:
{examples_text}

INSTRUCTIONS:
1. Generate a valid PostgreSQL query based on the user's question
2. Use proper JOIN clauses when accessing multiple tables
3. Include appropriate WHERE, GROUP BY, and ORDER BY clauses
4. Use aggregate functions (SUM, AVG, COUNT) when needed
5. Return ONLY the SQL query without any explanation or markdown
6. Do NOT use DROP, DELETE, UPDATE, or TRUNCATE
7. Always use table aliases for clarity
8. Consider NULL values in your logic

Question: {question}

SQL Query (return ONLY the SQL, no explanation):"""
        
        # Generate SQL
        response = self.llm(full_prompt)
        
        # Extract SQL from response
        sql = self._extract_sql(response)
        return sql
    
    def _generate_with_concise_chain(self, question: str) -> str:
        """Generate SQL using concise strategy"""
        # Retrieve fewer examples
        similar_examples = self.vector_db.retrieve_similar(question, k=3)
        examples_text = self.vector_db.format_examples_for_prompt(similar_examples)
        
        # Use concise chain
        response = self.concise_chain.run(
            examples=examples_text,
            question=question
        )
        
        # Extract SQL from response
        sql = self._extract_sql(response)
        return sql
    
    def _extract_sql(self, response: str) -> str:
        """Extract SQL query from model response"""
        # Remove markdown code blocks if present
        if "```sql" in response:
            response = response.split("```sql")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        
        # Remove common prefixes
        response = re.sub(r'^(SQL:|Query:|Answer:)\s*', '', response, flags=re.IGNORECASE)
        
        # Clean up whitespace
        response = response.strip()
        
        # Remove any trailing semicolon and re-add one
        response = response.rstrip(';')
        response += ';'
        
        return response
    
    def generate_with_agent(self, question: str) -> str:
        """
        Generate SQL using LangChain agent (more advanced)
        This allows the agent to use tools to gather information
        """
        if self.agent is None:
            # Fallback to regular generation if agent not available
            return self.generate_sql(question, strategy="detailed")
        
        result = self.agent.run(question)
        return self._extract_sql(result)

# Example usage
if __name__ == "__main__":
    generator = NL2SQLGenerator()
    
    test_questions = [
        "Show total sales by category",
        "Find top 5 customers by spending",
        "What products are out of stock?"
    ]
    
    for q in test_questions:
        print(f"\nQuestion: {q}")
        
        # Test detailed strategy
        sql_detailed = generator.generate_sql(q, strategy="detailed")
        print(f"SQL (Detailed): {sql_detailed}")
        
        # Test concise strategy
        sql_concise = generator.generate_sql(q, strategy="concise")
        print(f"SQL (Concise): {sql_concise}")
