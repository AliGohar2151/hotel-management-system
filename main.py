import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random
import sqlite3
import os

# --- CORE DATA MODEL & MANAGER CLASS ---

class HotelManager:
    """Manages all hotel data and business logic."""
    def __init__(self, db_name="hotel.db"):
        self.db_name = db_name
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row # Allows accessing columns by name
        self._create_tables()
        if not self._is_db_populated():
            self._load_sample_data()

    def _create_tables(self):
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()
        # Customers Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL
            )''')
        # Rooms Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                room_number TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                price REAL NOT NULL,
                status TEXT NOT NULL
            )''')
        # Bookings Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                booking_id TEXT PRIMARY KEY,
                customer_id TEXT,
                room_number TEXT,
                check_in_date TEXT,
                check_out_date TEXT,
                status TEXT,
                price_per_night REAL,
                FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
                FOREIGN KEY (room_number) REFERENCES rooms (room_number)
            )''')
        self.conn.commit()

    def _is_db_populated(self):
        """Check if the rooms table has any data."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM rooms")
        return cursor.fetchone()[0] > 0

    def _generate_id(self, prefix):
        # This approach is simple but not robust for high-concurrency.
        # For a production system, use database-generated IDs (e.g., AUTOINCREMENT).
        if prefix == 'C':
            return f"C{random.randint(1000, 9999)}"
        elif prefix == 'R':
            return str(random.randint(101, 999)) # Simple generation for example
        elif prefix == 'B':
            return f"B{random.randint(50000, 99999)}"
        return None

    def _load_sample_data(self):
        # Sample Rooms (Only rooms remain)
        room_types = {
            "Standard": 100.00,
            "Deluxe": 150.00,
            "Suite": 250.00
        }
        for i in range(101, 111):
            room_number = str(i)
            room_type = random.choice(list(room_types.keys()))
            price = room_types[room_type]
            status = 'Available'
            self.conn.execute(
                "INSERT INTO rooms (room_number, type, price, status) VALUES (?, ?, ?, ?)",
                (room_number, room_type, price, status)
            )
        self.conn.commit()

    # --- ROOM MANAGEMENT ---
    
    def add_room(self, room_type, price):
        # In a real app, you'd ensure room_number is unique.
        cursor = self.conn.cursor()
        # Find the max room number and add 1
        cursor.execute("SELECT MAX(CAST(room_number AS INTEGER)) FROM rooms")
        max_room = cursor.fetchone()[0]
        room_number = str(max_room + 1) if max_room else "101"
        
        self.conn.execute(
            "INSERT INTO rooms (room_number, type, price, status) VALUES (?, ?, ?, ?)",
            (room_number, room_type, float(price), 'Available')
        )
        self.conn.commit()
        
    def update_room_details(self, room_number, new_type, new_price, new_status):
        """Updates room type, price, and status."""
        self.conn.execute(
            "UPDATE rooms SET type = ?, price = ?, status = ? WHERE room_number = ?",
            (new_type, float(new_price), new_status, room_number)
        )
        self.conn.commit()
        return True

    def update_room_status(self, room_number, status):
        """Used internally for check-in/out transitions."""
        self.conn.execute("UPDATE rooms SET status = ? WHERE room_number = ?", (status, room_number))
        self.conn.commit()
        return True

    def get_room_by_number(self, room_number):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM rooms WHERE room_number = ?", (room_number,))
        return cursor.fetchone()
    
    def get_room_price(self, room_number):
        room = self.get_room_by_number(room_number)
        return room['price'] if room else 0

    @property
    def rooms(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM rooms ORDER BY room_number")
        return [dict(row) for row in cursor.fetchall()]

    # --- CUSTOMER MANAGEMENT ---
    
    def add_customer(self, name, email, phone):
        customer_id = self._generate_id('C')
        self.conn.execute(
            "INSERT INTO customers (customer_id, name, email, phone) VALUES (?, ?, ?, ?)",
            (customer_id, name, email, phone)
        )
        self.conn.commit()
        return customer_id

    def update_customer(self, customer_id, new_name, new_email, new_phone):
        """Updates customer name, email, and phone."""
        self.conn.execute(
            "UPDATE customers SET name = ?, email = ?, phone = ? WHERE customer_id = ?",
            (new_name, new_email, new_phone, customer_id)
        )
        self.conn.commit()
        return True

    def get_customer_name(self, customer_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM customers WHERE customer_id = ?", (customer_id,))
        customer = cursor.fetchone()
        return customer['name'] if customer else 'Unknown'

    @property
    def customers(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM customers ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    # --- BOOKING & AVAILABILITY ---
    
    def add_booking(self, customer_id, room_number, check_in_date, check_out_date, status='Confirmed'):
        if check_in_date >= check_out_date: # Dates are datetime.date objects
            return False, "Check-out date must be after check-in date."

        room = self.get_room_by_number(room_number)
        if not room:
            return False, "Room not found."
            
        if not self.is_room_available(room_number, check_in_date.isoformat(), check_out_date.isoformat()):
            return False, f"Room {room_number} is already booked or occupied during this period."

        booking_id = self._generate_id('B')
        self.conn.execute(
            """INSERT INTO bookings (booking_id, customer_id, room_number, check_in_date, check_out_date, status, price_per_night)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (booking_id, customer_id, room_number, check_in_date.isoformat(), check_out_date.isoformat(), status, self.get_room_price(room_number))
        )
        self.conn.commit()
        return True, f"Booking {booking_id} confirmed."

    def is_room_available(self, room_number, new_check_in, new_check_out, booking_id_to_ignore=None):
        """Checks if a room is available, optionally ignoring a specific booking ID."""
        cursor = self.conn.cursor()
        query = """
            SELECT COUNT(*) FROM bookings
            WHERE room_number = ?
            AND status IN ('Confirmed', 'CheckedIn')
            AND check_out_date > ? -- new_check_in
            AND check_in_date < ? -- new_check_out
        """
        params = [room_number, new_check_in, new_check_out]

        if booking_id_to_ignore:
            query += " AND booking_id != ?"
            params.append(booking_id_to_ignore)

        cursor.execute(query, params)
        overlap_count = cursor.fetchone()[0]
        
        return overlap_count == 0

    def get_available_rooms(self, check_in_date, check_out_date):
        available_rooms = []
        for room in self.rooms:
            # Skip maintenance rooms
            if room['status'] == 'Maintenance':
                continue
                
            if self.is_room_available(room['room_number'], check_in_date.isoformat(), check_out_date.isoformat()):
                available_rooms.append(room)
        return available_rooms

    def update_booking(self, booking_id, new_room_number, new_check_in, new_check_out, new_status):
        booking_to_update = self.get_booking_by_id(booking_id)
        
        if not booking_to_update:
            return False, "Booking not found."
            
        if new_check_in >= new_check_out: # These are datetime.date objects
            return False, "Check-out date must be after check-in date."

        # 1. Check if the NEW room/dates conflict with OTHER bookings, ignoring this one
        if not self.is_room_available(new_room_number, new_check_in.isoformat(), new_check_out.isoformat(), booking_id_to_ignore=booking_id):
            return False, f"Room {new_room_number} is not available for the new dates/room."

        # 2. Handle room status transition if the room number or status changes
        old_room_number = booking_to_update['room_number']
        old_status = booking_to_update['status']
        
        # If the booking was CheckedIn, release the old room
        if old_status == 'CheckedIn':
            self.update_room_status(old_room_number, 'Available')
            
        # Set new room status based on the new status
        if new_status == 'CheckedIn':
            self.update_room_status(new_room_number, 'Occupied')
        elif new_status == 'Confirmed' or new_status == 'Cancelled' or new_status == 'CheckedOut':
            # Ensure the room is Available if the new status is not CheckedIn
            # This is safe because availability check passed
            pass
            
        # 3. Apply the updates
        self.conn.execute(
            """UPDATE bookings SET room_number = ?, check_in_date = ?, check_out_date = ?, status = ?, price_per_night = ?
               WHERE booking_id = ?""",
            (new_room_number, new_check_in.isoformat(), new_check_out.isoformat(), new_status, self.get_room_price(new_room_number), booking_id)
        )
        self.conn.commit()
        
        return True, f"Booking {booking_id} successfully updated."

    def get_booking_by_id(self, booking_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,))
        return cursor.fetchone()

    @property
    def bookings(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM bookings")
        # Convert date strings back to date objects
        all_bookings = []
        for row in cursor.fetchall():
            b = dict(row)
            b['check_in_date'] = datetime.strptime(b['check_in_date'], '%Y-%m-%d').date()
            b['check_out_date'] = datetime.strptime(b['check_out_date'], '%Y-%m-%d').date()
            all_bookings.append(b)
        return all_bookings

    # --- CHECK-IN / CHECK-OUT / CANCELLATION ---

    def check_in(self, booking_id):
        booking = self.get_booking_by_id(booking_id)
        if booking and booking['status'] == 'Confirmed':
            self.conn.execute("UPDATE bookings SET status = 'CheckedIn' WHERE booking_id = ?", (booking_id,))
            self.conn.commit()
            self.update_room_status(booking['room_number'], 'Occupied')
            return True
        return False

    def check_out(self, booking_id):
        booking = self.get_booking_by_id(booking_id)
        if booking and booking['status'] == 'CheckedIn':
            self.conn.execute("UPDATE bookings SET status = 'CheckedOut' WHERE booking_id = ?", (booking_id,))
            self.conn.commit()
            self.update_room_status(booking['room_number'], 'Available')
            return True
        return False
        
    def cancel_booking(self, booking_id):
        booking = self.get_booking_by_id(booking_id)
        if booking and booking['status'] == 'Confirmed':
            self.conn.execute("UPDATE bookings SET status = 'Cancelled' WHERE booking_id = ?", (booking_id,))
            self.conn.commit()
            return True
        return False


# --- REPORTING (Unchanged) ---

    def get_reports(self, start_date, end_date):
        report = {
            'total_revenue': 0.0,
            'occupied_nights': 0,
            'completed_bookings': 0,
            'cancelled_bookings': 0,
        }
        
        # Calculate occupancy and revenue
        for booking in self.bookings: # Uses the property getter
            b_in = booking['check_in_date']
            b_out = booking['check_out_date']
            status = booking['status']
            price = booking['price_per_night']
            
            # Determine the overlap period for the report timeframe
            start = max(b_in, start_date)
            end = min(b_out, end_date)
            
            if start < end:
                duration = (end - start).days
                
                # Revenue: Only count CheckedOut bookings for final revenue
                if status == 'CheckedOut':
                    report['total_revenue'] += duration * price
                    report['completed_bookings'] += 1
                
                # Occupancy: Count nights for Confirmed, CheckedIn, and CheckedOut bookings
                if status in ['Confirmed', 'CheckedIn', 'CheckedOut']:
                    report['occupied_nights'] += duration
                
                # Cancellations
                if status == 'Cancelled' and b_in >= start_date and b_in <= end_date:
                    report['cancelled_bookings'] += 1
                    
        
        # Calculate total available nights
        num_rooms = len(self.rooms)
        duration_days = (end_date - start_date).days
        total_nights = num_rooms * duration_days
        
        report['total_nights'] = total_nights
        
        if total_nights > 0:
            report['occupancy_rate'] = (report['occupied_nights'] / total_nights) * 100
        else:
            report['occupancy_rate'] = 0.0

        return report

# --- STREAMLIT UI COMPONENTS (Unchanged) ---

def display_rooms(manager):
    st.subheader("Current Room Inventory")
    if manager.rooms:
        df = pd.DataFrame(manager.rooms)
        # Apply conditional formatting for status for modern display
        st.dataframe(
            df, 
            column_order=['room_number', 'type', 'price', 'status'],
            column_config={
                'price': st.column_config.NumberColumn("Price/Night", format="€%.2f"),
                'status': st.column_config.TextColumn("Status"),
                'room_number': st.column_config.TextColumn("Room #"),
                'type': st.column_config.TextColumn("Room Type")
            },
            hide_index=True
        )
    else:
        st.info("No rooms registered yet.")

def display_bookings(manager, search_query=''):
    st.subheader("Booking Ledger")
    
    # Prepare data for display
    booking_data = []
    for b in manager.bookings: # Uses the property getter
        customer_name = manager.get_customer_name(b['customer_id'])
        booking_data.append({
            'ID': b['booking_id'],
            'Room': b['room_number'],
            'Customer': customer_name,
            'Check In': b['check_in_date'],
            'Check Out': b['check_out_date'],
            'Status': b['status'],
            'Price/Night': b['price_per_night']
        })
    
    df = pd.DataFrame(booking_data)
    
    # Filtering Logic (Search & Filtering Feature)
    if not df.empty and search_query:
        df_filtered = df[
            df['ID'].str.contains(search_query, case=False) |
            df['Room'].str.contains(search_query, case=False) |
            df['Customer'].str.contains(search_query, case=False) |
            df['Status'].str.contains(search_query, case=False)
        ]
    else:
        df_filtered = df

    if not df_filtered.empty:
        # Sort by Check In Date descending
        df_filtered = df_filtered.sort_values(by='Check In', ascending=False)
        
        st.dataframe(
            df_filtered, 
            use_container_width=True,
            column_config={
                'Price/Night': st.column_config.NumberColumn("Price/Night", format="€%.2f"),
            },
            hide_index=True
        )
    else:
        st.info("No bookings found matching the search criteria.")


# --- MAIN STREAMLIT APPLICATION ---

def main():
    st.set_page_config(
        page_title="Hotel Management System",
        page_icon="🏨",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize the Hotel Manager in session state for persistence
    if 'hotel_manager' not in st.session_state:
        # Define the path for the database file
        db_file = "hotel_management.db"
        st.session_state.hotel_manager = HotelManager(db_name=db_file)
        # Add a cleanup function for the database connection
        def cleanup():
            if 'hotel_manager' in st.session_state:
                st.session_state.hotel_manager.conn.close()
    
    manager = st.session_state.hotel_manager
    
    st.title("🏨 Horizon Hotel Manager")
    st.markdown("A Modern Management System powered by Streamlit.")

    # Main Tabs for Navigation
    tab_dashboard, tab_bookings, tab_rooms, tab_customers = st.tabs(
        ["Dashboard & Reports", "Booking Operations", "Room Management", "Customer Management"]
    )

    # --- TAB 1: DASHBOARD & REPORTS (Unchanged) ---
    with tab_dashboard:
        st.header("Hotel Performance Overview")
        
        col_dates = st.columns(2)
        today = datetime.now().date()
        
        report_start_date = col_dates[0].date_input("Report Start Date", today - timedelta(days=30))
        report_end_date = col_dates[1].date_input("Report End Date", today)
        
        # Ensure start is before end
        if report_start_date >= report_end_date:
            st.error("Report End Date must be after Start Date.")
            st.stop()
            
        reports = manager.get_reports(report_start_date, report_end_date)
        
        st.subheader("Key Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric(
            "Occupancy Rate", 
            f"{reports['occupancy_rate']:.2f}%", 
            f"{reports['occupied_nights']} nights used"
        )
        col2.metric("Total Revenue", f"€{reports['total_revenue']:,.2f}")
        col3.metric("Total Rooms", len(manager.rooms))
        col4.metric("Completed Bookings", reports['completed_bookings'])
        
        st.markdown("---")
        
        st.subheader("Room Availability Snapshot")
        
        # Automatic Room Availability Tracking - Status breakdown
        room_df = pd.DataFrame(manager.rooms)
        status_counts = room_df['status'].value_counts()
        
        status_data = pd.DataFrame({
            'Status': status_counts.index, 
            'Count': status_counts.values
        })
        
        col_chart, col_data = st.columns([2, 1])
        with col_chart:
            st.bar_chart(status_data, x='Status', y='Count', color="#4a90e2")
        with col_data:
            st.dataframe(status_data, hide_index=True, use_container_width=True)


    # --- TAB 2: BOOKING OPERATIONS (Updated with Modify Booking) ---
    with tab_bookings:
        st.header("Booking Management & Operations")
        
        op_tab_new, op_tab_list, op_tab_actions, op_tab_modify = st.tabs(["New Booking", "View & Search Bookings", "Check-In / Check-Out / Cancel", "Modify Booking"])
        
        # New Booking Section (Unchanged)
        with op_tab_new:
            st.subheader("Create a New Booking")
            
            if not manager.customers:
                st.warning("Please register a customer in the 'Customer Management' tab before creating a booking.")
            
            with st.form("new_booking_form"):
                col_in, col_out = st.columns(2)
                
                check_in = col_in.date_input("Check-in Date", datetime.now().date())
                check_out = col_out.date_input("Check-out Date", datetime.now().date() + timedelta(days=1))
                
                # Customer selection
                customer_options = {c['customer_id']: f"{c['name']} ({c['customer_id']})" for c in manager.customers}
                selected_customer_id = st.selectbox( # The .customers property is called here
                    "Select Customer",
                    options=list(customer_options.keys()),
                    format_func=lambda x: customer_options.get(x) if customer_options else "No Customers",
                    disabled=not bool(manager.customers)
                )

                # Available Room Search (Dynamic Feature)
                if check_in and check_out:
                    available_rooms = manager.get_available_rooms(check_in, check_out)
                    
                    if available_rooms:
                        room_options = {r['room_number']: f"Room {r['room_number']} ({r['type']} - €{r['price']:.2f}/night)" 
                                        for r in available_rooms}
                        selected_room_number = st.selectbox(
                            f"Available Rooms ({len(available_rooms)} found)",
                            options=list(room_options.keys()),
                            format_func=lambda x: room_options.get(x)
                        )
                    else:
                        st.warning("No rooms are available for the selected dates.")
                        selected_room_number = None
                else:
                    selected_room_number = None

                submitted = st.form_submit_button("Confirm Booking")
                
                if submitted:
                    if not selected_customer_id or not selected_room_number:
                        st.error("Please select a customer and available room.")
                    else:
                        success, message = manager.add_booking(
                            selected_customer_id, 
                            selected_room_number, 
                            check_in, 
                            check_out
                        )
                        if success:
                            st.success(f"Successfully created booking: {message}")
                        else:
                            st.error(f"Booking failed: {message}")

        # View & Search Bookings (Unchanged)
        with op_tab_list:
            search_term = st.text_input("Search Bookings (by ID, Room, Customer Name, or Status)", key="booking_search")
            display_bookings(manager, search_term)

        # Check-In / Check-Out / Cancel (Unchanged)
        with op_tab_actions:
            st.subheader("Booking Actions")
            
            action_col1, action_col2, action_col3 = st.columns(3)
            
            # Filter bookings that are Confirmed (ready for check-in)
            ready_for_check_in = [b for b in manager.bookings if b['status'] == 'Confirmed']
            
            if ready_for_check_in:
                ci_options = {b['booking_id']: f"{b['booking_id']} - {manager.get_customer_name(b['customer_id'])} (Room {b['room_number']})" for b in ready_for_check_in}
                selected_ci = action_col1.selectbox("Select Booking for Check-In", options=list(ci_options.keys()), format_func=lambda x: ci_options.get(x))
                
                if action_col1.button("✅ Check In"):
                    if manager.check_in(selected_ci):
                        st.success(f"Booking {selected_ci} successfully checked in. Room is now Occupied.")
                        st.rerun()
                    else:
                        st.error(f"Failed to check in booking {selected_ci}.")
            else:
                action_col1.info("No bookings confirmed for check-in.")
                
            # Filter bookings that are CheckedIn (ready for check-out)
            ready_for_check_out = [b for b in manager.bookings if b['status'] == 'CheckedIn']

            if ready_for_check_out:
                co_options = {b['booking_id']: f"{b['booking_id']} - {manager.get_customer_name(b['customer_id'])} (Room {b['room_number']})" for b in ready_for_check_out}
                selected_co = action_col2.selectbox("Select Booking for Check-Out", options=list(co_options.keys()), format_func=lambda x: co_options.get(x))
                
                if action_col2.button("🔑 Check Out"):
                    if manager.check_out(selected_co):
                        st.success(f"Booking {selected_co} successfully checked out. Room is now Available.")
                        st.rerun()
                    else:
                        st.error(f"Failed to check out booking {selected_co}.")
            else:
                action_col2.info("No guests currently checked in.")

            # Filter bookings that are Confirmed (can be cancelled)
            cancelable = [b for b in manager.bookings if b['status'] == 'Confirmed']

            if cancelable:
                cancel_options = {b['booking_id']: f"{b['booking_id']} - {manager.get_customer_name(b['customer_id'])} (Room {b['room_number']})" for b in cancelable}
                selected_cancel = action_col3.selectbox("Select Booking to Cancel", options=list(cancel_options.keys()), format_func=lambda x: cancel_options.get(x))
                
                if action_col3.button("❌ Cancel Booking"):
                    if manager.cancel_booking(selected_cancel):
                        st.success(f"Booking {selected_cancel} has been successfully cancelled.")
                        st.rerun()
                    else:
                        st.error(f"Failed to cancel booking {selected_cancel}.")
            else:
                action_col3.info("No confirmed bookings to cancel.")
                
        # Modify Booking Tab (NEW)
        with op_tab_modify:
            st.subheader("Modify Existing Booking Details")
            
            if manager.bookings:
                booking_options = {b['booking_id']: f"{b['booking_id']} - {manager.get_customer_name(b['customer_id'])} (Room {b['room_number']}, {b['check_in_date']} to {b['check_out_date']})" for b in manager.bookings}
                selected_booking_id = st.selectbox(
                    "Select Booking to Modify",
                    options=list(booking_options.keys()),
                    format_func=lambda x: booking_options.get(x),
                    key="modify_booking_select"
                )
                
                booking_to_modify = manager.get_booking_by_id(selected_booking_id)
                
                if booking_to_modify:
                    with st.form(f"modify_booking_form_{selected_booking_id}"):
                        st.markdown(f"**Current Guest:** {manager.get_customer_name(booking_to_modify['customer_id'])}")
                        
                        # Date Inputs
                        col_in_mod, col_out_mod = st.columns(2)
                        # Convert string dates from DB back to date objects for the widget
                        current_check_in = datetime.strptime(booking_to_modify['check_in_date'], '%Y-%m-%d').date()
                        current_check_out = datetime.strptime(booking_to_modify['check_out_date'], '%Y-%m-%d').date()
                        new_check_in = col_in_mod.date_input("New Check-in Date", current_check_in)
                        new_check_out = col_out_mod.date_input("New Check-out Date", current_check_out)
                        
                        # Status Input
                        all_statuses = ["Confirmed", "CheckedIn", "CheckedOut", "Cancelled"]
                        new_status = st.selectbox("New Status", all_statuses, 
                                                  index=all_statuses.index(booking_to_modify['status']))
                        
                        # Room Selection (using date objects for availability check)
                        # Get all rooms, then filter based on new dates, ignoring this booking
                        all_rooms = manager.rooms
                        available_room_numbers = [r['room_number'] for r in all_rooms if manager.is_room_available(r['room_number'], new_check_in.isoformat(), new_check_out.isoformat(), booking_id_to_ignore=selected_booking_id)]

                        current_room = booking_to_modify['room_number']
                        # Ensure the current room is available for selection
                        if current_room not in available_room_numbers:
                             available_room_numbers.insert(0, current_room)

                        if available_room_numbers:
                            room_options_mod = {r['room_number']: f"Room {r['room_number']} ({r['type']} - €{r['price']:.2f}/night)" 
                                            for r in all_rooms if r['room_number'] in available_room_numbers}

                            default_index = available_room_numbers.index(current_room) if current_room in available_room_numbers else 0
                            
                            new_room_number = st.selectbox(
                                f"New Room (Available for dates: {len(available_room_numbers)})",
                                options=available_room_numbers,
                                format_func=lambda x: room_options_mod.get(x, "Invalid Room"),
                                index=default_index
                            )
                        else:
                            st.warning("No available rooms for the selected dates.")
                            new_room_number = None

                        update_submitted = st.form_submit_button("Apply Booking Changes")

                        if update_submitted:
                            if new_room_number:
                                success, message = manager.update_booking(
                                    selected_booking_id, 
                                    new_room_number, 
                                    new_check_in, 
                                    new_check_out, 
                                    new_status
                                )
                                if success:
                                    st.success(f"Booking {selected_booking_id} updated successfully!")
                                    st.rerun()
                                else:
                                    st.error(f"Booking update failed: {message}")
                            else:
                                st.error("Cannot update: No room selected or available.")
                else:
                    st.info("Please select a booking to modify.")
            else:
                st.info("No bookings registered yet.")


    # --- TAB 3: ROOM MANAGEMENT (Updated with full room detail update) ---
    with tab_rooms:
        st.header("Room Inventory Management")
        
        col_add, col_status = st.columns([1, 2])
        
        with col_add:
            st.subheader("Add New Room")
            with st.form("add_room_form"):
                room_type = st.selectbox("Room Type", ["Standard", "Deluxe", "Suite"], key="add_room_type")
                price = st.number_input("Price per Night (€)", min_value=10.00, value=120.00, step=5.00, key="add_room_price")
                
                add_submitted = st.form_submit_button("Add Room")
                if add_submitted:
                    manager.add_room(room_type, price)
                    st.success(f"New {room_type} room added successfully!")
                    st.rerun()
                    
        with col_status:
            st.subheader("Update Room Details & Status")
            if manager.rooms:
                room_options = {r['room_number']: f"Room {r['room_number']} ({r['type']}, Status: {r['status']})" for r in manager.rooms}
                selected_room_num = st.selectbox(
                    "Select Room to Update", 
                    options=list(room_options.keys()),
                    format_func=lambda x: room_options.get(x),
                    key="update_room_select"
                )
                
                selected_room = manager.get_room_by_number(selected_room_num)
                
                if selected_room:
                    with st.form(f"update_room_form_{selected_room_num}"):
                        st.markdown(f"**Modify Details for Room {selected_room_num}:**")
                        
                        all_types = ["Standard", "Deluxe", "Suite"]
                        all_room_statuses = ["Available", "Occupied", "Maintenance"]
                        
                        new_type = st.selectbox("Room Type", all_types, index=all_types.index(selected_room['type']))
                        new_price = st.number_input("Price per Night (€)", min_value=10.00, value=selected_room['price'], step=5.00)
                        new_status = st.selectbox("Status", all_room_statuses, index=all_room_statuses.index(selected_room['status']))
                        
                        update_submitted = st.form_submit_button("Apply Room Changes")
                        
                        if update_submitted:
                            if manager.update_room_details(selected_room_num, new_type, new_price, new_status):
                                st.success(f"Room {selected_room_num} details and status updated successfully!")
                                st.rerun() 
                            else:
                                st.error(f"Could not update room {selected_room_num}.")
                else:
                    st.warning("Please select a room.")
            else:
                st.info("No rooms to update.")
        
        st.markdown("---")
        display_rooms(manager)


    # --- TAB 4: CUSTOMER MANAGEMENT (Updated with Customer Update) ---
    with tab_customers:
        st.header("Customer Database")
        
        col_form, col_list = st.columns([1, 2])

        with col_form:
            st.subheader("Register New Customer")
            with st.form("add_customer_form"):
                name = st.text_input("Full Name", key="new_cust_name")
                email = st.text_input("Email Address", key="new_cust_email")
                phone = st.text_input("Phone Number", key="new_cust_phone")
                
                customer_submitted = st.form_submit_button("Register Customer")
                
                if customer_submitted:
                    if name and email and phone:
                        manager.add_customer(name, email, phone)
                        st.success(f"Customer {name} registered successfully!")
                        st.rerun()
                    else:
                        st.error("All fields are required.")

        with col_list:
            st.subheader("Customer List")
            if manager.customers:
                customer_df = pd.DataFrame(manager.customers)
                st.dataframe(customer_df, use_container_width=True, hide_index=True)
            else:
                st.info("No customers registered yet.")

            st.markdown("---")
            st.subheader("Update Customer Details")
            
            if manager.customers:
                customer_options = {c['customer_id']: f"{c['name']} ({c['customer_id']})" for c in manager.customers}
                selected_customer_id = st.selectbox(
                    "Select Customer to Update", 
                    options=list(customer_options.keys()),
                    format_func=lambda x: customer_options.get(x),
                    key="update_cust_select"
                )
                
                customer_to_update = next((c for c in manager.customers if c['customer_id'] == selected_customer_id), None)
                
                if customer_to_update:
                    with st.form(f"update_customer_form_{selected_customer_id}"):
                        new_name = st.text_input("Full Name", value=customer_to_update['name'])
                        new_email = st.text_input("Email Address", value=customer_to_update['email'])
                        new_phone = st.text_input("Phone Number", value=customer_to_update['phone'])
                        
                        update_submitted = st.form_submit_button("Update Customer Info")
                        
                        if update_submitted:
                            if manager.update_customer(selected_customer_id, new_name, new_email, new_phone):
                                st.success(f"Customer {new_name} ({selected_customer_id}) updated successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to update customer.")
                
            else:
                st.info("Register a customer first to enable updates.")


if __name__ == "__main__":

    main()
