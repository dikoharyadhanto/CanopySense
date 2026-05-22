import os
import glob
import pandas as pd
import uuid

CSV_DIR = 'tests/result_output/historical'
SEED_FILE = 'database/seed.sql'

def generate_seed():
    all_csv_files = glob.glob(os.path.join(CSV_DIR, '*.csv'))
    
    # Extract unique block IDs and satellite data rows
    unique_blocks = set()
    satellite_inserts = []
    
    for file in all_csv_files:
        df = pd.read_csv(file)
        for _, row in df.iterrows():
            block_id = int(row['block_id'])
            unique_blocks.add(block_id)
            
            # format values for SQL
            acq_date = row['acquisition_date']
            sensor = row['sensor']
            cloud_cover = row['cloud_cover']
            ndvi = row['ndvi']
            evi = row['evi']
            ndre = row['ndre']
            savi = row['savi']
            gndvi = row['gndvi']
            features = row['features'].replace("'", "''") # escape single quotes
            
            satellite_inserts.append(
                f"({block_id}, '{acq_date}', '{sensor}', {cloud_cover}, {ndvi}, {evi}, {ndre}, {savi}, {gndvi}, '{features}')"
            )
            
    with open(SEED_FILE, 'w') as f:
        # 1. Company
        company_uuid = str(uuid.uuid4())
        f.write(f"INSERT INTO companies (id, company_id, company_name) VALUES (1, '{company_uuid}', 'PT CanopySense Demo');\n\n")
        
        # 2. User
        f.write("INSERT INTO users (id, company_id, email, full_name, username, password_hash, is_active) VALUES (1, 1, 'manager@canopysense.demo', 'Demo Manager', 'manager', 'dummy_hash', true);\n\n")
        
        # 3. User Role
        f.write("INSERT INTO user_company_roles (user_id, company_id, role) VALUES (1, 1, 'manager');\n\n")
        
        # 4. Estate
        f.write("INSERT INTO estates (id, company_id, name, code, geometry) VALUES (1, 1, 'Estate Alpha', 'EST-001', ST_GeomFromText('MULTIPOLYGONZ((( (107.0 -0.5 0, 107.5 -0.5 0, 107.5 -1.0 0, 107.0 -1.0 0, 107.0 -0.5 0) )))', 4326));\n\n")
        
        # 5. Afdeling
        f.write("INSERT INTO afdelings (id, estate_id, company_id, name, code, geometry) VALUES (1, 1, 1, 'Afdeling 1', 'AFD-001', ST_GeomFromText('MULTIPOLYGON((( (107.0 -0.5, 107.5 -0.5, 107.5 -1.0, 107.0 -1.0, 107.0 -0.5) )))', 4326));\n\n")
        
        # 6. Blocks
        f.write("INSERT INTO blocks (id, afdeling_id, company_id, name, code, geometry, plant_year, clone_type) VALUES\n")
        block_values = []
        for b_id in sorted(unique_blocks):
            # generate simple polygon for each block
            poly = f"ST_GeomFromText('POLYGON(({107.0 + b_id*0.001} -0.5, {107.001 + b_id*0.001} -0.5, {107.001 + b_id*0.001} -0.501, {107.0 + b_id*0.001} -0.501, {107.0 + b_id*0.001} -0.5))', 4326)"
            block_values.append(f"({b_id}, 1, 1, 'Block {b_id}', 'BLK-{b_id:03d}', {poly}, 2018, 'PB260')")
            
        f.write(",\n".join(block_values) + "\nON CONFLICT (id) DO NOTHING;\n\n")
        
        # 7. Satellite Data
        f.write("INSERT INTO satellite_data (block_id, acquisition_date, sensor, cloud_cover, ndvi, evi, ndre, savi, gndvi, features) VALUES\n")
        f.write(",\n".join(satellite_inserts) + "\nON CONFLICT (block_id, acquisition_date, sensor) DO NOTHING;\n")

if __name__ == '__main__':
    generate_seed()
    print('Successfully generated database/seed.sql')
