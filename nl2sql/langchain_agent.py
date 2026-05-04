from langchain_community.llms import Ollama
from langchain.agents import create_react_agent, AgentExecutor, create_tool_calling_agent
from langchain_core.tools import Tool
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.memory import ConversationBufferMemory
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from typing import Dict, List
import os

class LangChainSQLAgent:
    """
    Advanced LangChain agent for SQL generation with tool usage.
    Uses ReAct pattern to reason about SQL generation.
    """
    
    def __init__(self, 
                 model_name: str = "llama3.1:8b",
                 db_uri: str = "postgresql://user:password@localhost:5432/ecommerce"):
        
        # Initialize LLM
        self.llm = Ollama(
            model=model_name,
            temperature=0,
            base_url=os.getenv("OLLAMA_URL", "http://localhost:11434")
        )
        
        # Initialize database connection for LangChain
        try:
            self.db = SQLDatabase.from_uri(db_uri)
        except Exception as e:
            print(f"Warning: Could not connect to database: {e}")
            self.db = None
        
        # Initialize memory for conversational context
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Create tools
        self.tools = self._create_tools()
        
        # Initialize agent
        self.agent = self._create_agent()
        
        print("✓ LangChain SQL Agent initialized")
    
    def _create_tools(self) -> List[Tool]:
        """Create tools for the agent to use"""
        
        tools = []
        
        # Tool 1: Get table schema
        def get_table_schema(table_name: str) -> str:
            """Get the schema for a specific table"""
            if self.db:
                try:
                    return self.db.get_table_info([table_name])
                except:
                    return f"Could not retrieve schema for {table_name}"
            return "Database not connected"
        
        tools.append(Tool(
            name="GetTableSchema",
            func=get_table_schema,
            description="Useful for getting the schema of a specific database table. Input should be a table name like 'customers' or 'orders'."
        ))
        
        # Tool 2: List all tables
        def list_tables() -> str:
            """List all available tables in the database"""
            if self.db:
                try:
                    tables = self.db.get_usable_table_names()
                    return f"Available tables: {', '.join(tables)}"
                except:
                    return "Could not retrieve table list"
            return "Database not connected"
        
        tools.append(Tool(
            name="ListTables",
            func=list_tables,
            description="Lists all available tables in the database. Use this to see what tables are available."
        ))
        
        # Tool 3: Search similar queries (from vector DB)
        def search_similar_queries(question: str) -> str:
            """Search for similar SQL queries in the knowledge base"""
            from nl2sql.vector_db import VectorDBManager
            
            try:
                vector_db = VectorDBManager()
                similar = vector_db.retrieve_similar(question, k=3)
                
                result = "Similar queries from knowledge base:\n\n"
                for i, ex in enumerate(similar, 1):
                    result += f"{i}. Question: {ex['question']}\n"
                    result += f"   SQL: {ex['sql']}\n\n"
                
                return result
            except Exception as e:
                return f"Error searching similar queries: {e}"
        
        tools.append(Tool(
            name="SearchSimilarQueries",
            func=search_similar_queries,
            description="Search for similar SQL queries and examples from the knowledge base. Input should be the natural language question."
        ))
        
        # Tool 4: Validate SQL syntax
        def validate_sql(sql: str) -> str:
            """Validate SQL query syntax"""
            import sqlparse
            
            try:
                parsed = sqlparse.parse(sql)
                if not parsed:
                    return "Invalid SQL: Empty or malformed query"
                
                statement = parsed[0]
                if statement.get_type() != 'SELECT':
                    return "Invalid: Only SELECT queries are allowed"
                
                return "Valid SQL syntax"
            except Exception as e:
                return f"Invalid SQL: {str(e)}"
        
        tools.append(Tool(
            name="ValidateSQL",
            func=validate_sql,
            description="Validate the syntax of a SQL query. Input should be the complete SQL query string."
        ))
        
        return tools
    
    def _create_agent(self):
        """Create the ReAct agent"""
        
        # Agent system message
        system_message = """You are an expert SQL query generator for an e-commerce database.

Your task is to generate safe, efficient SQL queries from natural language questions.

Guidelines:
1. Use the ListTables tool to see available tables
2. Use GetTableSchema tool to understand table structures
3. Use SearchSimilarQueries to find relevant examples
4. Generate a PostgreSQL SELECT query
5. Use ValidateSQL to check your query before returning it
6. Return ONLY the final SQL query, nothing else

Safety rules:
- ONLY generate SELECT queries
- NO DROP, DELETE, UPDATE, or TRUNCATE
- Use proper JOINs and aliases
- Handle NULL values appropriately
- Use aggregate functions when needed

Think step by step and use tools to gather information before generating SQL.
"""
        
        # Create ReAct agent with the updated API
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        # Create executor
        executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=5,
            handle_parsing_errors=True
        )
        
        return executor
    
    def generate_sql(self, question: str) -> str:
        """
        Generate SQL query using the agent
        
        Args:
            question: Natural language question
            
        Returns:
            Generated SQL query
        """
        try:
            # Run the agent
            result = self.agent.run(question)
            
            # Extract SQL from result
            sql = self._extract_sql(result)
            return sql
            
        except Exception as e:
            print(f"Agent error: {e}")
            # Fallback to simple generation
            return self._fallback_generation(question)
    
    def _extract_sql(self, response: str) -> str:
        """Extract SQL query from agent response"""
        import re
        
        # Remove markdown code blocks
        if "```sql" in response:
            response = response.split("```sql")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        
        # Remove common prefixes
        response = re.sub(r'^(SQL:|Query:|Final Answer:|Answer:)\s*', '', response, flags=re.IGNORECASE | re.MULTILINE)
        
        # Extract just the SELECT statement
        lines = response.split('\n')
        sql_lines = []
        in_sql = False
        
        for line in lines:
            line = line.strip()
            if line.upper().startswith('SELECT'):
                in_sql = True
            if in_sql:
                sql_lines.append(line)
                if ';' in line:
                    break
        
        if sql_lines:
            sql = ' '.join(sql_lines)
        else:
            sql = response.strip()
        
        # Clean up
        sql = sql.strip()
        if not sql.endswith(';'):
            sql += ';'
        
        return sql
    
    def _fallback_generation(self, question: str) -> str:
        """Fallback generation without agent tools"""
        
        prompt = PromptTemplate(
            input_variables=["question"],
            template="""Generate a PostgreSQL SELECT query for this question:

Question: {question}

Tables available: customers, products, orders, order_items, categories, reviews, shipping, promotions

Return ONLY the SQL query:"""
        )
        
        chain = LLMChain(llm=self.llm, prompt=prompt)
        result = chain.run(question=question)
        
        return self._extract_sql(result)
    
    def chat(self, question: str) -> Dict:
        """
        Interactive chat interface with memory
        
        Args:
            question: User question
            
        Returns:
            Dict with SQL and explanation
        """
        sql = self.generate_sql(question)
        
        return {
            "question": question,
            "sql": sql,
            "status": "success"
        }

# Example usage
if __name__ == "__main__":
    # Initialize agent
    agent = LangChainSQLAgent()
    
    # Test questions
    test_questions = [
        "Show me all customers from USA",
        "What are the top 5 best selling products?",
        "Find total revenue by month",
    ]
    
    for question in test_questions:
        print(f"\n{'='*60}")
        print(f"Question: {question}")
        print(f"{'='*60}")
        
        sql = agent.generate_sql(question)
        print(f"\nGenerated SQL:\n{sql}")
