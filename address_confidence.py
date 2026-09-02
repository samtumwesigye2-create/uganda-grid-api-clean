import math

# UGAMAP hybrid approval policy. Automatic approval is intentionally conservative.
# It is based on confidence/collision risk, not simply a rural/city label.
AUTO_APPROVE_MIN_SCORE = 90
DENSE_REVIEW_RADIUS_M = 60.0
DENSE_REVIEW_COUNT = 4
DUPLICATE_RADIUS_M = 20.0


def _distance_m(lat1, lon1, lat2, lon2):
    r=6371000.0
    p1=math.radians(float(lat1));p2=math.radians(float(lat2))
    dp=math.radians(float(lat2)-float(lat1));dl=math.radians(float(lon2)-float(lon1))
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.atan2(math.sqrt(a),math.sqrt(1-a))


def evaluate_address_application(lat, lon, addresses, state, postal, gps_accuracy_m=None, is_special=False):
    reasons=[]
    score=100

    if not state:
        return {'score':0,'decision':'manual_review','auto_approve':False,'reasons':['outside_validated_state_geometry']}
    if state.get('ambiguous'):
        return {'score':0,'decision':'manual_review','auto_approve':False,'reasons':['state_boundary_ambiguous']}
    if not postal or not postal.get('zip_code'):
        score-=40;reasons.append('zip_unresolved')
    if is_special:
        return {'score':0,'decision':'manual_review','auto_approve':False,'reasons':['protected_or_special_location']}

    nearby=[]
    for a in addresses:
        try:
            alat=a.get('latitude');alon=a.get('longitude')
            if alat is None or alon is None:continue
            d=_distance_m(lat,lon,alat,alon)
            if d <= DENSE_REVIEW_RADIUS_M:nearby.append((d,a))
        except (TypeError,ValueError):continue
    nearby.sort(key=lambda x:x[0])

    nearest_m=round(nearby[0][0],2) if nearby else None
    duplicate_risk=nearest_m is not None and nearest_m <= DUPLICATE_RADIUS_M
    dense=len(nearby) >= DENSE_REVIEW_COUNT

    if duplicate_risk:
        score-=60;reasons.append('possible_existing_address_duplicate')
    if dense:
        score-=35;reasons.append('dense_address_environment')

    if gps_accuracy_m is None:
        score-=15;reasons.append('gps_accuracy_not_reported')
    else:
        try:
            acc=float(gps_accuracy_m)
            if acc > 20:score-=35;reasons.append('poor_gps_accuracy')
            elif acc > 10:score-=20;reasons.append('moderate_gps_accuracy')
            elif acc > 5:score-=8;reasons.append('acceptable_gps_accuracy')
        except (TypeError,ValueError):
            score-=15;reasons.append('invalid_gps_accuracy')

    score=max(0,min(100,score))
    auto=(score >= AUTO_APPROVE_MIN_SCORE and not duplicate_risk and not dense)
    if auto:reasons.append('high_confidence_low_collision_risk')
    return {
        'score':score,
        'decision':'auto_approve' if auto else 'manual_review',
        'auto_approve':auto,
        'reasons':reasons,
        'nearest_address_m':nearest_m,
        'nearby_address_count_60m':len(nearby),
        'policy':{'auto_approve_min_score':AUTO_APPROVE_MIN_SCORE,'duplicate_radius_m':DUPLICATE_RADIUS_M,'dense_radius_m':DENSE_REVIEW_RADIUS_M,'dense_count':DENSE_REVIEW_COUNT}
    }
