import json
import os
import tempfile
import unittest

import manual_zip_assignments as mz


POLYGON={
    "type":"Polygon",
    "coordinates":[[
        [32.50,0.30],[32.51,0.30],[32.51,0.31],[32.50,0.31],[32.50,0.30]
    ]],
}


class ManualZipStateOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_store=mz.STORE
        mz.STORE=os.path.join(self.tmp.name,"manual_zip_assignments.json")

    def tearDown(self):
        mz.STORE=self.old_store
        self.tmp.cleanup()

    def test_kampala_zip_cannot_be_assigned_to_albertine(self):
        with self.assertRaisesRegex(ValueError,"belongs to state KMP"):
            mz.create_assignment("20451","KLA","ALB","Wrong state",POLYGON)

    def test_state_is_derived_from_zip_region(self):
        item=mz.create_assignment("20451","KLA","","Kampala override",POLYGON)
        self.assertEqual(item["state_code"],"KMP")
        self.assertTrue(item["state_forced_by_zip"])
        matched=mz.match_point(0.305,32.505)
        self.assertEqual(matched["zip_code"],"20451")
        self.assertEqual(matched["state_code"],"KMP")

    def test_entebbe_zip_is_owned_by_kampala_metropolitan(self):
        item=mz.create_assignment("21421","ENT","KMP","Entebbe reserve",POLYGON)
        self.assertEqual(item["state_code"],"KMP")
        with self.assertRaisesRegex(ValueError,"belongs to state KMP"):
            mz.create_assignment("21422","ENT","LKV","Wrong Entebbe state",POLYGON)

    def test_existing_saved_assignment_is_canonicalized(self):
        raw=[{
            "zip_code":"29431",
            "postal_region":"HOI",
            "state_code":"KMP",
            "name":"Legacy bad metadata",
            "geometry":POLYGON,
            "manual":True,
        }]
        with open(mz.STORE,"w",encoding="utf-8") as f:
            json.dump(raw,f)
        loaded=mz.list_assignments()
        self.assertEqual(loaded[0]["state_code"],"ALB")
        self.assertTrue(loaded[0]["state_forced_by_zip"])


if __name__=="__main__":
    unittest.main()
