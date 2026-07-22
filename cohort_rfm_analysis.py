import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import os
import matplotlib.pyplot as plt

def run_analysis():
    print("Step 1: Loading raw CSV data into SQLite database...")
    conn = sqlite3.connect('cohort_analytics.db')
    
    customers_df = pd.read_csv('customers.csv')
    orders_df = pd.read_csv('orders.csv')
    
    customers_df.to_sql('customers', conn, if_exists='replace', index=False)
    orders_df.to_sql('orders', conn, if_exists='replace', index=False)
    
    print("Step 2: Computing Cohort Retention Matrix...")
    orders_completed = orders_df[orders_df['status'] == 'Completed'].copy()
    orders_completed['order_date'] = pd.to_datetime(orders_completed['order_date'])
    orders_completed['order_month'] = orders_completed['order_date'].dt.to_period('M')
    
    # First purchase per customer
    first_orders = orders_completed.groupby('customer_id')['order_date'].min().reset_index()
    first_orders['cohort_month'] = first_orders['order_date'].dt.to_period('M')
    
    # Merge to calculate month offset
    merged = pd.merge(orders_completed, first_orders[['customer_id', 'cohort_month']], on='customer_id')
    merged['month_index'] = (merged['order_month'].dt.year - merged['cohort_month'].dt.year) * 12 + \
                           (merged['order_month'].dt.month - merged['cohort_month'].dt.month)
    
    # Cohort Size
    cohort_sizes = first_orders.groupby('cohort_month')['customer_id'].nunique().to_frame('cohort_size')
    
    # Activity Matrix
    cohort_counts = merged.groupby(['cohort_month', 'month_index'])['customer_id'].nunique().unstack()
    
    # Retention Matrix (Percentage)
    cohort_matrix = cohort_counts.divide(cohort_sizes['cohort_size'], axis=0) * 100
    cohort_matrix = cohort_matrix.round(2)
    
    print("Step 3: Performing RFM Customer Segmentation...")
    ref_date = pd.to_datetime('2026-01-01')
    
    rfm = orders_completed.groupby('customer_id').agg({
        'order_date': lambda x: (ref_date - x.max()).days,
        'order_id': 'nunique',
        'order_value': 'sum'
    }).reset_index()
    
    rfm.columns = ['customer_id', 'recency_days', 'frequency', 'monetary_value']
    
    # RFM Scoring (1 to 5)
    rfm['r_score'] = pd.qcut(rfm['recency_days'], 5, labels=[5, 4, 3, 2, 1]).astype(int)
    rfm['f_score'] = pd.qcut(rfm['frequency'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm['m_score'] = pd.qcut(rfm['monetary_value'], 5, labels=[1, 2, 3, 4, 5]).astype(int)
    
    def classify_rfm(row):
        r, f, m = row['r_score'], row['f_score'], row['m_score']
        if r >= 4 and f >= 4 and m >= 4:
            return 'Champions'
        elif r >= 3 and f >= 3 and m >= 3:
            return 'Loyal Customers'
        elif r >= 4 and f <= 2:
            return 'Promising / New'
        elif r <= 2 and f >= 3 and m >= 3:
            return 'At Risk'
        elif r <= 2 and f <= 2:
            return 'Lost / Churned'
        else:
            return 'Need Attention'
            
    rfm['customer_segment'] = rfm.apply(classify_rfm, axis=1)
    
    segment_summary = rfm.groupby('customer_segment').agg(
        customer_count=('customer_id', 'count'),
        avg_recency_days=('recency_days', 'mean'),
        avg_orders_per_customer=('frequency', 'mean'),
        avg_total_spend=('monetary_value', 'mean'),
        total_revenue=('monetary_value', 'sum')
    ).reset_index()
    
    total_cust = len(rfm)
    segment_summary['segment_pct'] = (segment_summary['customer_count'] / total_cust * 100).round(2)
    segment_summary = segment_summary.sort_values(by='total_revenue', ascending=False)

    print("Step 4: Exporting formatted Excel Workbook (Cohort_RFM_Report.xlsx)...")
    
    # Executive KPIs
    total_rev = orders_completed['order_value'].sum()
    total_orders = len(orders_completed)
    avg_m1_retention = cohort_matrix[1].mean() if 1 in cohort_matrix.columns else 0.0
    
    kpi_df = pd.DataFrame([
        {'Metric': 'Total Revenue', 'Value': f"${total_rev:,.2f}"},
        {'Metric': 'Total Customers', 'Value': f"{total_cust:,}"},
        {'Metric': 'Total Completed Orders', 'Value': f"{total_orders:,}"},
        {'Metric': 'Avg Month-1 Retention Rate', 'Value': f"{avg_m1_retention:.2f}%"},
        {'Metric': 'Report Generated Date', 'Value': datetime.now().strftime('%Y-%m-%d')}
    ])

    with pd.ExcelWriter('Cohort_RFM_Report.xlsx', engine='openpyxl') as writer:
        kpi_df.to_excel(writer, sheet_name='Executive Summary', index=False)
        cohort_matrix.to_excel(writer, sheet_name='Cohort Retention Matrix (%)')
        segment_summary.to_excel(writer, sheet_name='RFM Segmentation Summary', index=False)
        rfm.to_excel(writer, sheet_name='Customer RFM Scores', index=False)

    print("Step 5: Generating visual charts with Matplotlib...")
    
    # Chart 1: Cohort Retention Matrix Heatmap
    plt.figure(figsize=(12, 7))
    matrix_data = cohort_matrix.values
    plt.imshow(matrix_data, cmap='YlGnBu', aspect='auto')
    
    # Annotate percentage numbers inside heatmap cells
    for i in range(matrix_data.shape[0]):
        for j in range(matrix_data.shape[1]):
            val = matrix_data[i, j]
            if not np.isnan(val):
                text_color = 'white' if val > 50 else 'black'
                plt.text(j, i, f"{val:.1f}%", ha='center', va='center', color=text_color, fontsize=8, fontweight='bold')
                
    plt.title('Monthly Customer Cohort Retention Rate (%)', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('Months Since Initial Purchase', fontsize=11, labelpad=10)
    plt.ylabel('Cohort Month', fontsize=11, labelpad=10)
    plt.xticks(ticks=range(cohort_matrix.shape[1]), labels=cohort_matrix.columns)
    plt.yticks(ticks=range(len(cohort_matrix.index)), labels=[str(m) for m in cohort_matrix.index])
    plt.colorbar(label='Retention Rate (%)')
    plt.tight_layout()
    plt.savefig('cohort_retention_heatmap.png', dpi=300)
    plt.close()

    # Chart 2: RFM Customer Segment Breakdown Bar Chart
    plt.figure(figsize=(10, 5))
    bars = plt.barh(segment_summary['customer_segment'], segment_summary['customer_count'], color='#2b5c8f')
    plt.title('Customer Distribution by RFM Segment', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('Number of Customers', fontsize=11)
    plt.ylabel('Customer Segment', fontsize=11)
    plt.gca().invert_yaxis()
    
    # Add count labels next to bars
    for bar in bars:
        width = bar.get_width()
        plt.text(width + (total_cust * 0.01), bar.get_y() + bar.get_height()/2, f"{int(width):,}", ha='left', va='center', fontsize=9, fontweight='bold')
        
    plt.tight_layout()
    plt.savefig('rfm_segment_distribution.png', dpi=300)
    plt.close()

    print("Analysis completed successfully! Outputs saved to 'Cohort_RFM_Report.xlsx', 'cohort_retention_heatmap.png', and 'rfm_segment_distribution.png'.")

if __name__ == '__main__':
    run_analysis()

