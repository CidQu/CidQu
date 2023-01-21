import csv

# Create an empty list to store the updated rows
# Güncellenecek satırların boş bir listesi
updated_rows = []

keys_to_check = 'KEY'
value_to_update = 'TRANSLATED'

main_file = 'main.csv'
update_file = 'update.csv'

# Read main.csv file
# main.csv dosyasını açma
with open(main_file, 'r', encoding='utf-8') as main_file:
    main_reader = csv.DictReader(main_file)
    fieldnames = main_reader.fieldnames
    # Read update.csv file
    # update.csv dosyasını açma
    with open(update_file, 'r', encoding='utf-8') as update_file:
        update_reader = csv.DictReader(update_file)
        update_rows = list(update_reader)
        for main_row in main_reader:
            for update_row in update_rows:
                # Check if 'KEY' column matches
                # KEY'ler uyuşuyor mu diye kontrol
                if main_row[keys_to_check] == update_row[keys_to_check]:
                    # Update 'translated' column in main_row
                    # Oluşuyorsa TRANSLATED olan column'u değiştir
                    main_row[value_to_update] = update_row[value_to_update]
                    break
            # Append the updated main_row to the list
            # Değişiklikleri kaydet
            updated_rows.append(main_row)
    # Write updated main.csv
    # Yaptığımız tüm işlemleri bitirme
    with open(main_file, 'w', newline='', encoding='utf-8') as main_file:
        main_writer = csv.DictWriter(main_file, fieldnames=fieldnames)
        main_writer.writeheader()
        for row in updated_rows:
            main_writer.writerow(row)