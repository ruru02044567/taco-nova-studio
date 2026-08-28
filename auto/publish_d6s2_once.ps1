Set-Location "C:\Users\TUF Gaming\Desktop\我的專案\財富密碼"
python auto\pipeline.py ok d6s2 --by-xianxian *> auto\publish_d6s2_log.txt
python auto\sync_ledger.py *>> auto\publish_d6s2_log.txt
schtasks /delete /tn TacoNova-PublishD6s2 /f
