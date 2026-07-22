import csv
import random
from datetime import datetime, timedelta

def generate_dataset():
    random.seed(42)
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 31)
    total_days = (end_date - start_date).days

    num_customers = 5000
    countries = ['United States', 'United Kingdom', 'Germany', 'Canada', 'Australia', 'France']
    country_weights = [0.45, 0.20, 0.15, 0.10, 0.05, 0.05]

    customers = []
    customer_cohorts = {}

    for cid in range(1001, 1001 + num_customers):
        signup_day_offset = int(random.triangular(0, total_days * 0.7, total_days))
        signup_date = start_date + timedelta(days=signup_day_offset)
        country = random.choices(countries, weights=country_weights)[0]
        customers.append({
            'customer_id': cid,
            'signup_date': signup_date.strftime('%Y-%m-%d'),
            'country': country
        })
        customer_cohorts[cid] = signup_date

    orders = []
    order_id = 50001

    for cust in customers:
        cid = cust['customer_id']
        signup_dt = customer_cohorts[cid]
        
        # Initial order on or shortly after signup date
        first_order_date = signup_dt + timedelta(days=random.randint(0, 3))
        if first_order_date <= end_date:
            order_val = round(random.uniform(25.0, 250.0), 2)
            orders.append({
                'order_id': order_id,
                'customer_id': cid,
                'order_date': first_order_date.strftime('%Y-%m-%d %H:%M:%S'),
                'order_value': order_val,
                'status': 'Completed'
            })
            order_id += 1

        # Determine customer repeat profile
        profile_rand = random.random()
        if profile_rand < 0.25:
            # One-time buyer (25%)
            repeat_count = 0
        elif profile_rand < 0.65:
            # Occasional buyer (40%)
            repeat_count = random.randint(1, 4)
        elif profile_rand < 0.90:
            # Regular buyer (25%)
            repeat_count = random.randint(5, 12)
        else:
            # VIP / Power buyer (10%)
            repeat_count = random.randint(13, 30)

        curr_date = first_order_date
        for _ in range(repeat_count):
            days_gap = int(random.expovariate(1.0 / 35.0)) + 3
            curr_date += timedelta(days=days_gap)
            if curr_date > end_date:
                break
            
            # 5% chance of cancelled/refunded order
            status = 'Completed' if random.random() > 0.05 else 'Cancelled'
            val = round(random.uniform(15.0, 350.0), 2)
            if profile_rand >= 0.90:
                val = round(random.uniform(100.0, 600.0), 2)

            orders.append({
                'order_id': order_id,
                'customer_id': cid,
                'order_date': curr_date.strftime('%Y-%m-%d %H:%M:%S'),
                'order_value': val,
                'status': status
            })
            order_id += 1

    # Write customers.csv
    with open('customers.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['customer_id', 'signup_date', 'country'])
        writer.writeheader()
        writer.writerows(customers)

    # Write orders.csv
    with open('orders.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['order_id', 'customer_id', 'order_date', 'order_value', 'status'])
        writer.writeheader()
        writer.writerows(orders)

    print(f"Dataset generated successfully: {len(customers)} customers, {len(orders)} orders.")

if __name__ == '__main__':
    generate_dataset()
