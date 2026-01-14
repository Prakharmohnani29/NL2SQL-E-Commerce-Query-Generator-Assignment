import json
import time
from typing import Dict, List
import pandas as pd
from nl2sql.generator import NL2SQLGenerator
from nl2sql.validator import QueryValidator
from nl2sql.executor import QueryExecutor

class NL2SQLEvaluator:
    """
    Comprehensive evaluation framework for NL2SQL system.
    Tests generation, validation, and execution across difficulty levels.
    """
    
    def __init__(self, generator: NL2SQLGenerator, validator: QueryValidator, 
                 executor: QueryExecutor):
        self.generator = generator
        self.validator = validator
        self.executor = executor
        self.results = []
    
    def run_evaluation(self, test_queries_path: str = "tests/test_queries.json") -> pd.DataFrame:
        """Run complete evaluation on test suite"""
        
        # Load test queries
        with open(test_queries_path, 'r') as f:
            test_queries = json.load(f)
        
        print(f"Starting evaluation with {len(test_queries)} test queries...\n")
        
        for i, test in enumerate(test_queries, 1):
            print(f"[{i}/{len(test_queries)}] Testing: {test['question']}")
            
            result = self._evaluate_single_query(test)
            self.results.append(result)
            
            # Print result
            status = "✓" if result['execution_success'] else "✗"
            print(f"  {status} Generation: {result['generation_time_ms']:.0f}ms | "
                  f"Execution: {result['execution_time_ms']:.0f}ms | "
                  f"Valid: {result['validation_passed']}")
            
            if not result['execution_success']:
                print(f"  Error: {result['error_type']}")
            print()
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(self.results)
        return df
    
    def _evaluate_single_query(self, test: Dict) -> Dict:
        """Evaluate a single test query"""
        result = {
            'id': test['id'],
            'question': test['question'],
            'difficulty': test['difficulty'],
            'category': test['category'],
            'generated_sql': None,
            'validation_passed': False,
            'execution_success': False,
            'generation_time_ms': 0,
            'execution_time_ms': 0,
            'rows_returned': 0,
            'error_type': None,
            'error_message': None,
            'first_attempt_success': False
        }
        
        try:
            # Step 1: Generate SQL
            gen_start = time.time()
            generated_sql = self.generator.generate_sql(
                test['question'], 
                strategy="detailed"
            )
            gen_time = (time.time() - gen_start) * 1000
            
            result['generated_sql'] = generated_sql
            result['generation_time_ms'] = gen_time
            
            # Step 2: Validate SQL
            is_valid, error_msg, validation_details = self.validator.validate(generated_sql)
            result['validation_passed'] = is_valid
            
            if not is_valid:
                result['error_type'] = 'validation_error'
                result['error_message'] = error_msg
                return result
            
            # Step 3: Execute SQL
            success, data, error, exec_metrics = self.executor.execute(generated_sql)
            
            result['execution_success'] = success
            result['execution_time_ms'] = exec_metrics.get('execution_time_ms', 0)
            result['first_attempt_success'] = (exec_metrics.get('attempt_number', 1) == 1)
            
            if success:
                result['rows_returned'] = len(data) if data else 0
            else:
                result['error_type'] = exec_metrics.get('error_type', 'execution_error')
                result['error_message'] = error
            
        except Exception as e:
            result['error_type'] = 'system_error'
            result['error_message'] = str(e)
        
        return result
    
    def generate_report(self, df: pd.DataFrame) -> Dict:
        """Generate comprehensive evaluation report"""
        
        total_queries = len(df)
        
        report = {
            'summary': {
                'total_queries': total_queries,
                'successful_executions': df['execution_success'].sum(),
                'validation_failures': (~df['validation_passed']).sum(),
                'execution_failures': ((df['validation_passed']) & (~df['execution_success'])).sum(),
                'success_rate_percent': (df['execution_success'].sum() / total_queries * 100),
                'first_attempt_success_rate': (df['first_attempt_success'].sum() / total_queries * 100),
            },
            'performance': {
                'avg_generation_time_ms': df['generation_time_ms'].mean(),
                'avg_execution_time_ms': df[df['execution_success']]['execution_time_ms'].mean(),
                'max_generation_time_ms': df['generation_time_ms'].max(),
                'max_execution_time_ms': df['execution_time_ms'].max(),
            },
            'by_difficulty': {},
            'by_category': {},
            'error_analysis': {}
        }
        
        # Performance by difficulty
        for difficulty in df['difficulty'].unique():
            subset = df[df['difficulty'] == difficulty]
            report['by_difficulty'][difficulty] = {
                'total': len(subset),
                'success': subset['execution_success'].sum(),
                'success_rate': (subset['execution_success'].sum() / len(subset) * 100)
            }
        
        # Performance by category
        for category in df['category'].unique():
            subset = df[df['category'] == category]
            report['by_category'][category] = {
                'total': len(subset),
                'success': subset['execution_success'].sum(),
                'success_rate': (subset['execution_success'].sum() / len(subset) * 100)
            }
        
        # Error analysis
        failed_queries = df[~df['execution_success']]
        if len(failed_queries) > 0:
            error_counts = failed_queries['error_type'].value_counts()
            report['error_analysis'] = error_counts.to_dict()
        
        return report
    
    def print_report(self, report: Dict):
        """Print formatted evaluation report"""
        
        print("=" * 80)
        print("NL2SQL EVALUATION REPORT")
        print("=" * 80)
        
        print("\n📊 SUMMARY")
        print("-" * 80)
        summary = report['summary']
        print(f"Total Queries:           {summary['total_queries']}")
        print(f"Successful Executions:   {summary['successful_executions']}")
        print(f"Validation Failures:     {summary['validation_failures']}")
        print(f"Execution Failures:      {summary['execution_failures']}")
        print(f"Success Rate:            {summary['success_rate_percent']:.1f}%")
        print(f"First Attempt Success:   {summary['first_attempt_success_rate']:.1f}%")
        
        print("\n⚡ PERFORMANCE METRICS")
        print("-" * 80)
        perf = report['performance']
        print(f"Avg Generation Time:     {perf['avg_generation_time_ms']:.2f}ms")
        print(f"Avg Execution Time:      {perf['avg_execution_time_ms']:.2f}ms")
        print(f"Max Generation Time:     {perf['max_generation_time_ms']:.2f}ms")
        print(f"Max Execution Time:      {perf['max_execution_time_ms']:.2f}ms")
        
        print("\n📈 PERFORMANCE BY DIFFICULTY")
        print("-" * 80)
        for difficulty, stats in report['by_difficulty'].items():
            print(f"{difficulty.upper():12} | "
                  f"Total: {stats['total']:2} | "
                  f"Success: {stats['success']:2} | "
                  f"Rate: {stats['success_rate']:5.1f}%")
        
        print("\n🏷️  PERFORMANCE BY CATEGORY")
        print("-" * 80)
        for category, stats in sorted(report['by_category'].items()):
            print(f"{category:30} | "
                  f"Total: {stats['total']:2} | "
                  f"Success: {stats['success']:2} | "
                  f"Rate: {stats['success_rate']:5.1f}%")
        
        if report['error_analysis']:
            print("\n❌ ERROR ANALYSIS")
            print("-" * 80)
            for error_type, count in report['error_analysis'].items():
                print(f"{error_type:30} | Count: {count}")
        
        print("\n" + "=" * 80)
    
    def save_results(self, df: pd.DataFrame, output_path: str = "tests/test_results.md"):
        """Save detailed results to markdown file"""
        
        with open(output_path, 'w') as f:
            f.write("# NL2SQL Test Results\n\n")
            
            f.write("## Detailed Test Results\n\n")
            f.write("| ID | Question | Difficulty | Success | Generation (ms) | Execution (ms) | Error |\n")
            f.write("|----|----------|------------|---------|-----------------|----------------|-------|\n")
            
            for _, row in df.iterrows():
                status = "✓" if row['execution_success'] else "✗"
                error = row['error_type'] if row['error_type'] else "-"
                
                f.write(f"| {row['id']} | {row['question'][:50]}... | "
                       f"{row['difficulty']} | {status} | "
                       f"{row['generation_time_ms']:.0f} | "
                       f"{row['execution_time_ms']:.0f} | "
                       f"{error} |\n")
            
            f.write("\n## Failed Queries\n\n")
            failed = df[~df['execution_success']]
            
            for _, row in failed.iterrows():
                f.write(f"### Query {row['id']}: {row['question']}\n\n")
                f.write(f"**Generated SQL:**\n```sql\n{row['generated_sql']}\n```\n\n")
                f.write(f"**Error Type:** {row['error_type']}\n\n")
                f.write(f"**Error Message:** {row['error_message']}\n\n")
        
        print(f"✓ Results saved to {output_path}")

# Example usage
if __name__ == "__main__":
    from nl2sql.generator import NL2SQLGenerator
    from nl2sql.validator import QueryValidator
    from nl2sql.executor import QueryExecutor
    
    # Initialize components
    generator = NL2SQLGenerator(model_name="llama3.1:8b")
    
    schema = generator.schema  # Use schema from generator
    validator = QueryValidator(schema)
    
    db_config = {
        'host': 'localhost',
        'database': 'ecommerce',
        'user': 'user',
        'password': 'password'
    }
    executor = QueryExecutor(db_config)
    
    # Run evaluation
    evaluator = NL2SQLEvaluator(generator, validator, executor)
    results_df = evaluator.run_evaluation()
    
    # Generate and print report
    report = evaluator.generate_report(results_df)
    evaluator.print_report(report)
    
    # Save results
    evaluator.save_results(results_df)
    
    executor.close()