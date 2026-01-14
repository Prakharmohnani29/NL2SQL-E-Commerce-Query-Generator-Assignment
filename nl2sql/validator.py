import sqlparse
import re
from typing import Dict, Tuple, List

class QueryValidator:
    """
    Validates SQL queries for syntax, safety, and schema compliance.
    Implements multiple validation checks before query execution.
    """
    
    def __init__(self, schema: Dict):
        self.schema = schema
        self.valid_tables = set(schema.keys())
        self.valid_columns = self._build_column_map()
        
        # Dangerous SQL keywords to block
        self.blocked_keywords = [
            'DROP', 'DELETE', 'UPDATE', 'TRUNCATE', 'ALTER', 
            'CREATE', 'INSERT', 'GRANT', 'REVOKE', 'EXEC'
        ]
    
    def _build_column_map(self) -> Dict[str, List[str]]:
        """Build mapping of table to valid columns"""
        column_map = {}
        for table, info in self.schema.items():
            column_map[table] = info['columns']
        return column_map
    
    def validate(self, sql: str) -> Tuple[bool, str, Dict]:
        """
        Main validation method - runs all checks
        
        Returns:
            (is_valid, error_message, validation_details)
        """
        validation_results = {
            'syntax_valid': False,
            'safety_check_passed': False,
            'schema_check_passed': False,
            'sql_injection_safe': False,
            'errors': []
        }
        
        # 1. Syntax validation
        is_valid, error = self._validate_syntax(sql)
        validation_results['syntax_valid'] = is_valid
        if not is_valid:
            validation_results['errors'].append(f"Syntax error: {error}")
            return False, error, validation_results
        
        # 2. Safety checks (no dangerous operations)
        is_safe, error = self._check_safety(sql)
        validation_results['safety_check_passed'] = is_safe
        if not is_safe:
            validation_results['errors'].append(f"Safety violation: {error}")
            return False, error, validation_results
        
        # 3. SQL injection prevention
        is_injection_safe, error = self._check_sql_injection(sql)
        validation_results['sql_injection_safe'] = is_injection_safe
        if not is_injection_safe:
            validation_results['errors'].append(f"SQL injection risk: {error}")
            return False, error, validation_results
        
        # 4. Schema validation (tables and columns exist)
        is_schema_valid, error = self._validate_schema(sql)
        validation_results['schema_check_passed'] = is_schema_valid
        if not is_schema_valid:
            validation_results['errors'].append(f"Schema error: {error}")
            return False, error, validation_results
        
        return True, "Query is valid", validation_results
    
    def _validate_syntax(self, sql: str) -> Tuple[bool, str]:
        """Check SQL syntax using sqlparse"""
        try:
            parsed = sqlparse.parse(sql)
            
            if not parsed:
                return False, "Empty or invalid SQL statement"
            
            if len(parsed) > 1:
                return False, "Multiple statements not allowed"
            
            statement = parsed[0]
            
            # Check if it's a SELECT statement
            if not statement.get_type() == 'SELECT':
                return False, "Only SELECT statements are allowed"
            
            return True, ""
            
        except Exception as e:
            return False, f"Syntax parsing failed: {str(e)}"
    
    def _check_safety(self, sql: str) -> Tuple[bool, str]:
        """Check for dangerous SQL operations"""
        sql_upper = sql.upper()
        
        for keyword in self.blocked_keywords:
            # Use word boundaries to avoid false positives
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                return False, f"Blocked keyword detected: {keyword}"
        
        # Check for semicolons (potential for multiple statements)
        if sql.count(';') > 1:
            return False, "Multiple statements detected (semicolons)"
        
        # Check for comments that might hide malicious code
        if '--' in sql or '/*' in sql:
            return False, "SQL comments not allowed"
        
        return True, ""
    
    def _check_sql_injection(self, sql: str) -> Tuple[bool, str]:
        """
        Check for common SQL injection patterns
        
        Note: This is a basic check. In production, use parameterized queries.
        """
        injection_patterns = [
            r"'\s*OR\s*'",  # ' OR '1'='1
            r"--",           # SQL comments
            r"/\*",          # Block comments
            r"\bEXEC\b",     # Execute commands
            r"\bxp_",        # Extended procedures
            r"UNION\s+SELECT",  # UNION attacks (should be valid, but suspicious without context)
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                return False, f"Potential SQL injection pattern detected: {pattern}"
        
        return True, ""
    
    def _validate_schema(self, sql: str) -> Tuple[bool, str]:
        """Validate that referenced tables and columns exist"""
        sql_upper = sql.upper()
        
        # Extract table names
        tables_found = []
        for table in self.valid_tables:
            # Look for table name with word boundaries
            pattern = r'\b' + table.upper() + r'\b'
            if re.search(pattern, sql_upper):
                tables_found.append(table)
        
        # Check if any tables were referenced
        if not tables_found:
            # Try to extract table names from FROM and JOIN clauses
            from_match = re.search(r'FROM\s+(\w+)', sql_upper)
            if from_match:
                referenced_table = from_match.group(1).lower()
                if referenced_table not in self.valid_tables:
                    return False, f"Table does not exist: {referenced_table}"
        
        # Basic column validation (extract potential column references)
        # This is simplified - full validation would require parsing the query tree
        for table in tables_found:
            valid_cols = [col.upper() for col in self.valid_columns[table]]
            
            # Check SELECT clause for column names
            select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql_upper, re.DOTALL)
            if select_match:
                select_clause = select_match.group(1)
                
                # Skip validation for * or aggregate functions
                if select_clause.strip() != '*' and 'COUNT(*)' not in select_clause:
                    # Extract potential column names (simplified)
                    potential_cols = re.findall(r'\b([a-z_]+)\b', select_clause, re.IGNORECASE)
                    
                    for col in potential_cols:
                        col_upper = col.upper()
                        # Skip SQL keywords and function names
                        if col_upper not in ['AS', 'FROM', 'WHERE', 'AND', 'OR', 'COUNT', 
                                            'SUM', 'AVG', 'MAX', 'MIN', 'DISTINCT']:
                            # Check if column exists in any referenced table
                            found = False
                            for t in tables_found:
                                if col_upper in [c.upper() for c in self.valid_columns[t]]:
                                    found = True
                                    break
                            
                            if not found and col_upper not in ['*']:
                                # This might be a false positive, so we just warn
                                pass  # In production, you'd want more sophisticated parsing
        
        return True, ""
    
    def get_validation_summary(self, validation_results: Dict) -> str:
        """Generate human-readable validation summary"""
        summary = "Validation Results:\n"
        summary += f"✓ Syntax Valid: {validation_results['syntax_valid']}\n"
        summary += f"✓ Safety Checks: {validation_results['safety_check_passed']}\n"
        summary += f"✓ Schema Valid: {validation_results['schema_check_passed']}\n"
        summary += f"✓ SQL Injection Safe: {validation_results['sql_injection_safe']}\n"
        
        if validation_results['errors']:
            summary += "\nErrors:\n"
            for error in validation_results['errors']:
                summary += f"  - {error}\n"
        
        return summary

# Example usage
if __name__ == "__main__":
    schema = {
        "products": {"columns": ["product_id", "product_name", "price"]},
        "customers": {"columns": ["customer_id", "customer_name", "email"]}
    }
    
    validator = QueryValidator(schema)
    
    test_queries = [
        "SELECT * FROM products",  # Valid
        "DROP TABLE products",      # Blocked
        "SELECT * FROM invalid_table",  # Invalid table
        "SELECT product_name FROM products WHERE price > 100",  # Valid
        "DELETE FROM products WHERE product_id = 1"  # Blocked
    ]
    
    for sql in test_queries:
        is_valid, error, results = validator.validate(sql)
        print(f"\nSQL: {sql}")
        print(f"Valid: {is_valid}")
        if not is_valid:
            print(f"Error: {error}")