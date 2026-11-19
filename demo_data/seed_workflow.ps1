# Adds recovery-workflow scenarios to the DEMO database through the public API (real matching pipeline, no fake scores).
$b = "http://127.0.0.1:8000/api/v1"; $pw = "Demo12345!"; $root = "E:\Work\OpenHeart_Surgery\data"
$items = @{}; Import-Csv "$root\items.csv" | % { $items[$_.report_id] = $_ }
function Hdr($e) { @{Authorization = "Bearer " + (Invoke-RestMethod "$b/auth/login" -Method Post -ContentType "application/json" -Body (@{email=$e;password=$pw}|ConvertTo-Json)).access_token} }
$finder = Hdr "finder@demo.test"; $owner = Hdr "owner@demo.test"; $staff = Hdr "staff@demo.test"
function Add-Found($id, $custody, $dir) {
  $i = $items[$id]; $f = @{category=$i.category; item_name=$i.category; custody_status=$custody; location=$i.location_name; image=(Get-Item "$root\Images\$($i.image_filename)")}
  if ($i.description) { $f.description = $i.description }
  if ($i.latitude) { $f.latitude = $i.latitude; $f.longitude = $i.longitude }
  if ($dir) { $f.directions = $dir }
  $r = Invoke-RestMethod "$b/reports/found" -Method Post -Headers $finder -Form $f; "FOUND $id -> $($r.report_code) matches=$($r.matches_created)"
}
function Add-Lost($id, [bool]$photo) {
  $i = $items[$id]; $f = @{category=$i.category; item_name=$i.category; description=$i.description; location=$i.location_name}
  if ($i.latitude) { $f.latitude = $i.latitude; $f.longitude = $i.longitude }
  if ($photo) { $f.image = Get-Item "$root\Images\$($i.image_filename)" }
  $r = Invoke-RestMethod "$b/reports/lost" -Method Post -Headers $owner -Form $f; "LOST  $id -> $($r.report_code) photo=$photo matches=$($r.matches_created)"
}
function Top-Match($lostCode) {
  $all = (Invoke-WebRequest "$b/matches" -Headers $owner -UseBasicParsing).Content | ConvertFrom-Json
  $all | ? { $_.lost_report.report_code -eq $lostCode } | Sort-Object rank | Select-Object -First 1
}
function Staff-Post($rid, $action, $body) {
  Invoke-RestMethod "$b/staff/recovery-requests/$rid/$action" -Method Post -Headers $staff -ContentType "application/json" -Body ($body | ConvertTo-Json -Depth 5) | Out-Null
}
Add-Found F015 LEFT_WHERE_FOUND "Next to the library entrance, on the left bench"
Add-Found F016 LEFT_WHERE_FOUND $null
Add-Found F020 AWAITING_DEPOSIT_CONFIRMATION $null
Add-Found F021 TEMPORARILY_HOLDING $null
Add-Found F025 TEMPORARILY_HOLDING "Handed to the canteen counter"
Add-Found F030 LEFT_WHERE_FOUND $null
Add-Lost L015 $true
Add-Lost L020 $true
Add-Lost L025 $false
Add-Lost L030 $true
$lostCodes = (Invoke-RestMethod "$b/reports/mine" -Headers $owner).lost | % { "$($_.report_code)|$($_.item_name)|$($_.description)" } | Where-Object { $_ -match "headphones|Smartphones|mouse|notebook" }
$map = @{}
foreach ($l in (Invoke-RestMethod "$b/reports/mine" -Headers $owner).lost) { foreach ($k in @("headphones","Smartphones","mouse","notebook")) { if (("$($l.category) $($l.description)") -match $k -and $l.status -eq "ACTIVE") { $map[$k] = $l.report_code } } }
$map.GetEnumerator() | % { "lost report for $($_.Key): $($_.Value)" }

# 1) pending claim with a photo as evidence
$m = Top-Match $map["headphones"]
$c = Invoke-RestMethod "$b/matches/$($m.id)/interest" -Method Post -Headers $owner -ContentType "application/json" -Body (@{proof="Sony headphones, left earcup has a small scratch"; distinguishing_features="Scratch on the left earcup, my initials on the headband"; additional_info="Lost after the Monday lab"}|ConvertTo-Json)
Invoke-RestMethod "$b/recovery-requests/$($c.id)/evidence" -Method Post -Headers $owner -Form @{note="Photo of my headphones at home"; image=(Get-Item "$root\Images\L015.jpg")} | Out-Null
"PENDING claim #$($c.id) on $($map['headphones'])"
# 2) claim where staff asked for more evidence
$m = Top-Match $map["Smartphones"]
$c = Invoke-RestMethod "$b/matches/$($m.id)/interest" -Method Post -Headers $owner -ContentType "application/json" -Body (@{proof="Light-blue iPhone without a case"}|ConvertTo-Json)
Staff-Post $c.id "review" @{note="Photo only shows the rear cameras"}
Staff-Post $c.id "request-evidence" @{message="Please tell us the lock-screen wallpaper and send a photo of the box or receipt."}
"EVIDENCE-REQUESTED claim #$($c.id) on $($map['Smartphones'])"
# 3) approved claim awaiting collection
$m = Top-Match $map["mouse"]
$c = Invoke-RestMethod "$b/matches/$($m.id)/interest" -Method Post -Headers $owner -ContentType "application/json" -Body (@{proof="Black Dell mouse with the white logo near the back"; distinguishing_features="Left button slightly worn"}|ConvertTo-Json)
Staff-Post $c.id "notes" @{note="Description matches the finder's photo; owner knew about the worn button."}
Staff-Post $c.id "approve" @{note="Verified details"; collection=@{name="Security Desk, Main Gate"; address="Main Gate, Campus Road (open 9:00-17:00)"; latitude=16.4975; longitude=80.5002; instructions="Bring your student ID. Ask for the lost-and-found box."}}
"APPROVED claim #$($c.id) awaiting collection on $($map['mouse'])"
