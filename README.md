# 🏨 Horizon Hotel Manager

A modern, web-based Hotel Management System built with Python and Streamlit. This application provides a user-friendly interface for managing hotel rooms, customers, and bookings, complete with a performance dashboard and reporting features.

---

## ✨ Features

- **Dashboard & Reports**: View key performance indicators like occupancy rate, total revenue, and completed bookings over any date range. Visualize room status distribution.
- **Room Management**: Add new rooms, update existing room details (type, price, status), and view the complete room inventory.
- **Customer Management**: Register new customers and update their contact information.
- **Booking Operations**:
  - Create new bookings by selecting a customer, dates, and an available room.
  - View, search, and filter all past and present bookings.
  - Modify existing bookings (change dates, room, or status).
  - Perform key actions: Check-In, Check-Out, and Cancel bookings.
- **Data Persistence**: All data is stored locally in a SQLite database (`hotel_management.db`), ensuring data is saved between sessions.

---

## 🛠️ Technologies Used

- **Python**: The core programming language.
- **Streamlit**: For building the interactive web application interface.
- **Pandas**: Used for data manipulation and display.
- **SQLite**: For the relational database management.

---

## 🚀 Getting Started

Follow these instructions to get a copy of the project up and running on your local machine.

### Prerequisites

- Python 3.8 or newer
- Pip (Python package installer)

### Installation & Setup

1. **Clone the repository:**
   ```sh
   git clone https://github.com/AliGohar2151/hotel-management-system
   cd hotel-management-system
   ```
2. **Install the required packages:**
   ```sh
   pip install -r requirements.txt
   ```
3. **Run the Streamlit application:**
   ```sh
   streamlit run main.py
   ```
4. Open your web browser and navigate to the local URL provided by Streamlit (usually `http://localhost:8501`).
