from flask import Flask, render_template, request, jsonify
import re
import os
import pandas as pd
from PyPDF2 import PdfReader

app = Flask(__name__)

# Configure a folder for uploaded files
app.config['UPLOAD_FOLDER'] = './uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def extract_dishes_from_pdf(file_path):
    # Load the PDF
    reader = PdfReader(file_path)
    text = ""

    # Extract text from all pages
    for page in reader.pages:
        text += page.extract_text()

    # Merge fragmented text
    text = text.replace("\n", " ")

    # Refined regex for dish names
    dish_pattern = r"\b([A-Za-z]+(?: [A-Za-z]+)+)\b"

    # Find matches
    all_matches = re.findall(dish_pattern, text)

    # Filter irrelevant items
    ignore_keywords = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", 
                       "Per Plate", "Served", "Calories", "Breakfast", "Lunch", "Dinner", "Snack"}

    filtered_dishes = [
        match for match in all_matches
        if len(match.split()) > 1 and match not in ignore_keywords
    ]

    return sorted(set(filtered_dishes))  # Return unique and sorted dishes


def match_dishes_with_calories(dishes, dataset_path):
    # Load the dataset
    df = pd.read_csv(dataset_path)

    # Ensure consistent casing for matching
    df["Dish"] = df["Dish"].str.lower()
    dishes = [dish.lower() for dish in dishes]

    # Match dishes with their calorie data
    matched_dishes = df[df["Dish"].isin(dishes)]

    return matched_dishes


def recommend_menu(user_preference, matched_dishes):
    if "Diet" not in matched_dishes.columns:
        raise ValueError("The 'Diet' column is missing in the dataset.")
    
    if "Calories" not in matched_dishes.columns or "Protein" not in matched_dishes.columns or \
       "Fats" not in matched_dishes.columns or "Sugars" not in matched_dishes.columns:
        raise ValueError("Required nutritional columns (Calories, Protein, Fat, Sugar) are missing in the dataset.")
    
    # Filter dishes based on user preference
    filtered_dishes = matched_dishes[matched_dishes["Diet"].str.contains(user_preference, case=False, na=False)]

    # Generate recommendations for breakfast, lunch, snacks, and dinner
    menu = {
        "Breakfast": [],
        "Lunch": [],
        "Snacks": [],
        "Dinner": []
    }

    nutrition_info = {
        "Breakfast": {"Calories": 0, "Protein": 0, "Fat": 0, "Sugar": 0},
        "Lunch": {"Calories": 0, "Protein": 0, "Fat": 0, "Sugar": 0},
        "Snacks": {"Calories": 0, "Protein": 0, "Fat": 0, "Sugar": 0},
        "Dinner": {"Calories": 0, "Protein": 0, "Fat": 0, "Sugar": 0}
    }

    # Sample dishes for each meal type
    for meal in menu.keys():
        meal_dishes = filtered_dishes[filtered_dishes["Category"].str.contains(meal, case=False, na=False)]
        
        # Ensure that we don't try to sample more dishes than available
        sample_size = min(len(meal_dishes), 7)  # Sample as many as possible, but no more than 7

        if sample_size > 0:
            selected_dishes = meal_dishes.sample(n=sample_size, replace=False)  # Avoid duplicates

            for _, dish_row in selected_dishes.iterrows():
                menu[meal].append(dish_row["Dish"])

                # Convert values to numeric (handling possible non-numeric characters like 'g' or missing values)
                calories = pd.to_numeric(dish_row["Calories"], errors='coerce')  # Convert to number, replace errors with NaN
                
                protein = dish_row["Protein"].replace('g', '') if isinstance(dish_row["Protein"], str) else str(dish_row["Protein"])
                fat = dish_row["Fats"].replace('g', '') if isinstance(dish_row["Fats"], str) else str(dish_row["Fats"])
                sugar = dish_row["Sugars"].replace('g', '') if isinstance(dish_row["Sugars"], str) else str(dish_row["Sugars"])

                # Convert to numeric after replacing 'g' and handle missing values
                protein = pd.to_numeric(protein, errors='coerce')
                fat = pd.to_numeric(fat, errors='coerce')
                sugar = pd.to_numeric(sugar, errors='coerce')

                # Default NaN to 0 if the conversion failed
                calories = calories if not pd.isna(calories) else 0
                protein = protein if not pd.isna(protein) else 0
                fat = fat if not pd.isna(fat) else 0
                sugar = sugar if not pd.isna(sugar) else 0

                # Add nutritional info
                nutrition_info[meal]["Calories"] += calories
                nutrition_info[meal]["Protein"] += protein
                nutrition_info[meal]["Fat"] += fat
                nutrition_info[meal]["Sugar"] += sugar

    return menu, nutrition_info


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        # Retrieve file from form input
        file = request.files["menu_pdf"]
        
        # Save the file to the 'uploads' directory
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # Load dataset (you can update this as needed)
        dataset_path = r"expanded_hostel_menufinal.csv"

        # Extract dishes from the uploaded menu PDF
        dishes = extract_dishes_from_pdf(file_path)

        # Match dishes with calorie data
        matched_dishes = match_dishes_with_calories(dishes, dataset_path)

        if matched_dishes.empty:
            return jsonify({"error": "No matching dishes found in the dataset."})

        # User preference for diet
        user_preference = request.form["diet_preference"]

        # Get the recommended menu
        weekly_menu, nutrition_info = recommend_menu(user_preference, matched_dishes)

        # Cleanup: remove the uploaded file
        os.remove(file_path)

        return render_template("menu.html", menu=weekly_menu, nutrition_info=nutrition_info)

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
