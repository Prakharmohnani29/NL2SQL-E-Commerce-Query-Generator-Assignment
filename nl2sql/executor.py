import psycopg2
from psycopg2 import sql
from typing import Dict, List, Tuple, Optional
import time

class QueryExecutor:
    """
    Executes validated SQL queries with self-correction capability.
    Tracks execution metrics and handles errors gracefully.
    """
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.connection = None
        self.execution_stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'retries': 0,
            'total_execution_time': 0
        }
        
        self._connect()
    
    def _connect(self):
        """Establish database connection"""
        try:
            self.connection = psycopg2.connect(
                host=self.db_config.get('host', 'localhost'),
                port=self.db_config.get('port', 5432),
                database=self.db_config.get('database', 'ecommerce'),
                user=self.db_config.get('user', 'user'),
                password=self.db_config.get('password', 'password')
            )
            print("✓ Database connection established")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            raise
    
    def execute(self, sql_query: str, max_retries: int = 2) -> Tuple[bool, Optional[List[Dict]], Optional[str], Dict]:
        """
        Execute SQL query with retry logic
        
        Args:
            sql_query: SQL query to execute
            max_retries: Maximum number of retry attempts
            
        Returns:
            (success, results, error_message, execution_metrics)
        """
        self.execution_stats['total_queries'] += 1
        
        attempt = 0
        last_error = None
        
        while attempt <= max_retries:
            try:
                start_time = time.time()
                
                # Execute query
                cursor = self.connection.cursor()
                cursor.execute(sql_query)
                
                # Fetch results
                if cursor.description:  # SELECT query returns results
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    results = [dict(zip(columns, row)) for row in rows]
                else:
                    results = []
                
                execution_time = (time.time() - start_time) * 1000  # milliseconds
                
                cursor.close()
                self.connection.commit()
                
                # Update stats
                self.execution_stats['successful_queries'] += 1
                self.execution_stats['total_execution_time'] += execution_time
                if attempt > 0:
                    self.execution_stats['retries'] += 1
                
                metrics = {
                    'execution_time_ms': round(execution_time, 2),
                    'rows_returned': len(results),
                    'attempt_number': attempt + 1
                }
                
                return True, results, None, metrics
                
            except psycopg2.Error as e:
                attempt += 1
                last_error = str(e)
                
                # Rollback failed transaction
                self.connection.rollback()
                
                # If we've exhausted retries, return error
                if attempt > max_retries:
                    self.execution_stats['failed_queries'] += 1
                    
                    metrics = {
                        'execution_time_ms': 0,
                        'rows_returned': 0,
                        'attempt_number': attempt,
                        'error_type': type(e).__name__
                    }
                    
                    return False, None, last_error, metrics
                
                # Otherwise, prepare for retry
                print(f"Query failed (attempt {attempt}), retrying...")
                time.sleep(0.5)  # Brief delay before retry
            
            except Exception as e:
                self.execution_stats['failed_queries'] += 1
                
                metrics = {
                    'execution_time_ms': 0,
                    'rows_returned': 0,
                    'attempt_number': attempt + 1,
                    'error_type': type(e).__name__
                }
                
                return False, None, str(e), metrics
    
    def execute_with_correction(self, sql_query: str, generator, question: str) -> Tuple[bool, Optional[List[Dict]], str]:
        """
        Execute query with self-correction capability
        If query fails, send error back to LLM for correction
        
        Args:
            sql_query: Initial SQL query
            generator: NL2SQL generator instance
            question: Original natural language question
            
        Returns:
            (success, results, final_sql_or_error)
        """
        # Try initial query
        success, results, error, metrics = self.execute(sql_query)
        
        if success:
            return True, results, sql_query
        
        # If failed, try self-correction
        print(f"Query failed: {error}")
        print("Attempting self-correction...")
        
        # Create correction prompt
        correction_prompt = f"""
The following SQL query failed with an error:

SQL: {sql_query}
Error: {error}

Original Question: {question}

Please generate a corrected SQL query that fixes this error.
Return ONLY the corrected SQL query.
"""
        
        try:
            # Generate corrected query
            corrected_sql = generator.generate_sql(correction_prompt, strategy="detailed")
            
            # Try corrected query (no further retries)
            success, results, error, metrics = self.execute(corrected_sql, max_retries=0)
            
            if success:
                print("✓ Self-correction successful!")
                return True, results, corrected_sql
            else:
                return False, None, f"Correction failed: {error}"
                
        except Exception as e:
            return False, None, f"Self-correction error: {str(e)}"
    
    def get_statistics(self) -> Dict:
        """Get execution statistics"""
        stats = self.execution_stats.copy()
        
        if stats['total_queries'] > 0:
            stats['success_rate'] = (stats['successful_queries'] / stats['total_queries']) * 100
            
        if stats['successful_queries'] > 0:
            stats['avg_execution_time_ms'] = stats['total_execution_time'] / stats['successful_queries']
        
        return stats
    
    def reset_statistics(self):
        """Reset execution statistics"""
        self.execution_stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'retries': 0,
            'total_execution_time': 0
        }
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            print("✓ Database connection closed")

# Example usage
if __name__ == "__main__":
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'ecommerce',
        'user': 'user',
        'password': 'password'
    }
    
    executor = QueryExecutor(db_config)
    
    # Test query
    sql = "SELECT * FROM products LIMIT 5"
    success, results, error, metrics = executor.execute(sql)
    
    if success:
        print(f"Query successful! Returned {len(results)} rows")
        print(f"Execution time: {metrics['execution_time_ms']}ms")
    else:
        print(f"Query failed: {error}")
    
    # Print statistics
    print("\nExecution Statistics:")
    print(executor.get_statistics())
    
    executor.close()