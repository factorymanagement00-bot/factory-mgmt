import json
import os

# ============================
# DATABASE FILE
# ============================
DB_FILE = "factory_db.json"

# If DB doesn't exist, create one
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w") as f:
        json.dump({"customers": [], "orders": [], "inventory": [], "jobs": []}, f, indent=4)


# ============================
# LOAD & SAVE FUNCTIONS
# ============================
def load_db():
    with open(DB_FILE, "r") as f:
        return json.load(f)


def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ============================
# MENU FUNCTIONS
# ============================

def add_customer():
    name = input("Customer name: ")
    phone = input("Phone number: ")

    db = load_db()
    db["customers"].append({"name": name, "phone": phone})
    save_db(db)

    print("✔ Customer added!\n")


def add_order():
    customer = input("Customer name: ")
    product = input("Product name: ")
    quantity = input("Quantity: ")
    amount = input("Amount: ")

    db = load_db()
    db["orders"].append({
        "customer": customer,
        "product": product,
        "quantity": quantity,
        "amount": amount,
        "status": "Pending"
    })

    save_db(db)
    print("✔ Order added!\n")


def add_inventory():
    item = input("Item name: ")
    stock = input("Stock quantity: ")

    db = load_db()
    db["inventory"].append({"item": item, "stock": stock})
    save_db(db)

    print("✔ Inventory item added!\n")


def add_job():
    job_name = input("Job name: ")
    job_type = input("Job type: ")
    phone = input("Phone number: ")
    amount = input("Amount: ")

    db = load_db()
    db["jobs"].append({
        "job_name": job_name,
        "job_type": job_type,
        "phone": phone,
        "amount": amount
    })

    save_db(db)
    print("✔ Small job added!\n")


def view_all():
    db = load_db()
    print("\n===== CUSTOMERS =====")
    for c in db["customers"]:
        print(c)

    print("\n===== ORDERS =====")
    for o in db["orders"]:
        print(o)

    print("\n===== INVENTORY =====")
    for i in db["inventory"]:
        print(i)

    print("\n===== SMALL JOBS =====")
    for j in db["jobs"]:
        print(j)
    print()


# ============================
# MAIN MENU LOOP
# ============================

def main():
    while True:
        print("""
============================
   FACTORY MANAGEMENT APP
============================
1. Add Customer
2. Add Order
3. Add Inventory
4. Add Small Job
5. View All Records
6. Exit
""")

        choice = input("Choose an option: ")

        if choice == "1":
            add_customer()
        elif choice == "2":
            add_order()
        elif choice == "3":
            add_inventory()
        elif choice == "4":
            add_job()
        elif choice == "5":
            view_all()
        elif choice == "6":
            print("Exiting...")
            break
        else:
            print("❌ Invalid choice, try again.\n")


if __name__ == "__main__":
    main()
