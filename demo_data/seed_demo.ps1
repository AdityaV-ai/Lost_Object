# Seeds the demo database through the public API (same path the UI uses). Run with servers up.
$b = "http://127.0.0.1:8000/api/v1"; $pw = "Demo12345!"
$root = "E:\Work\OpenHeart_Surgery\data"
$items = @{}; Import-Csv "$root\items.csv" | ForEach-Object { $items[$_.report_id] = $_ }
function Tok($e) { (Invoke-RestMethod "$b/auth/login" -Method Post -ContentType "application/json" -Body (@{email=$e;password=$pw}|ConvertTo-Json)).access_token }
$finder = @{Authorization = "Bearer $(Tok 'finder@demo.test')"}
$owner  = @{Authorization = "Bearer $(Tok 'owner@demo.test')"}

function Add-Found($id, $custody) {
  $i = $items[$id]; $f = @{category=$i.category; item_name=$i.category; custody_status=$custody; location=$i.location_name}
  if ($i.description) { $f.description = $i.description }
  if ($i.latitude) { $f.latitude = $i.latitude; $f.longitude = $i.longitude }
  $f.image = Get-Item "$root\Images\$($i.image_filename)"
  $r = Invoke-RestMethod "$b/reports/found" -Method Post -Headers $finder -Form $f
  "FOUND $id -> $($r.report_code) custody=$($r.custody_status) matches=$($r.matches_created)"
}
function Add-Lost($id, [bool]$photo) {
  $i = $items[$id]; $f = @{category=$i.category; item_name=$i.category; description=$i.description; location=$i.location_name}
  if ($i.latitude) { $f.latitude = $i.latitude; $f.longitude = $i.longitude }
  if ($photo) { $f.image = Get-Item "$root\Images\$($i.image_filename)" }
  $r = Invoke-RestMethod "$b/reports/lost" -Method Post -Headers $owner -Form $f
  "LOST  $id -> $($r.report_code) photo=$photo matches=$($r.matches_created)"
}
Add-Found F001 TEMPORARILY_HOLDING
Add-Found F002 LEFT_WHERE_FOUND
Add-Found F003 AWAITING_DEPOSIT_CONFIRMATION
Add-Found F006 TEMPORARILY_HOLDING
Add-Found F007 LEFT_WHERE_FOUND
Add-Lost L001 $true
Add-Lost L002 $true
Add-Lost L003 $false
Add-Lost L006 $true
Add-Lost L007 $false
