# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

import json
import mango

class QueryMethodTestsMixin:
    def verify_post_query_equivalence(self, request_body, partition=None):
        body = json.dumps(request_body)
        headers = {
            "Content-Type": "application/json",
        }
        if partition:
            path = self.db.path([f"_partition/{partition}/_find"])
        else:
            path = self.db.path("_find")
            
        post = self.db.sess.request(
            "POST",
            path,
            data=body,
            headers=headers,
        )
        query = self.db.sess.request(
            "QUERY",
            path,
            data=body,
            headers=headers,
        )
        
        post.raise_for_status()
        query.raise_for_status()
        
        self.assertEqual(post.json(), query.json())

    def test_query_method_equivalence(self):
        # 1. Simple selector
        self.verify_post_query_equivalence({"selector": {"age": {"$gt": 20}}})
        # 2. Nested selector
        self.verify_post_query_equivalence({
            "selector": {"$and": [{"age": {"$gt": 20}}, {"status": "active"}]}
        })
        # 3. In selector
        self.verify_post_query_equivalence({
            "selector": {"age": {"$in": [25, 35]}}
        })
        # 4. Projection
        self.verify_post_query_equivalence({
            "selector": {"age": {"$gt": 20}},
            "fields": ["name", "status"]
        })

    def test_query_method_explain_exclusion(self):
        body = json.dumps({"selector": {"age": {"$gt": 20}}})
        headers = {"Content-Type": "application/json"}
        r = self.db.sess.request("QUERY", self.db.path("_explain"), data=body, headers=headers)
        self.assertEqual(r.status_code, 405)

    def test_query_method_errors(self):
        # Malformed JSON with application/json header
        invalid_body = "{invalid_json}"
        headers = {"Content-Type": "application/json"}
        
        post = self.db.sess.request("POST", self.db.path("_find"), data=invalid_body, headers=headers)
        query = self.db.sess.request("QUERY", self.db.path("_find"), data=invalid_body, headers=headers)
        
        # Explicitly assert expected status code 400
        self.assertEqual(post.status_code, 400)
        self.assertEqual(query.status_code, 400)
        
        post_json = post.json()
        query_json = query.json()
        
        # Assert keys exist before comparing
        self.assertIn("error", post_json)
        self.assertIn("error", query_json)
        self.assertIn("reason", post_json)
        self.assertIn("reason", query_json)
        
        self.assertEqual(post_json["error"], query_json["error"])
        self.assertEqual(post_json["reason"], query_json["reason"])

    def test_content_type_parity(self):
        # Invalid Content-Type
        body = json.dumps({"selector": {"age": {"$gt": 20}}})
        headers = {"Content-Type": "text/plain"}
        
        post = self.db.sess.request("POST", self.db.path("_find"), data=body, headers=headers)
        query = self.db.sess.request("QUERY", self.db.path("_find"), data=body, headers=headers)
        
        # Explicitly assert expected status code 415
        self.assertEqual(post.status_code, 415)
        self.assertEqual(query.status_code, 415)
        
        post_json = post.json()
        query_json = query.json()
        
        # Assert keys exist before comparing
        self.assertIn("error", post_json)
        self.assertIn("error", query_json)
        self.assertIn("reason", post_json)
        self.assertIn("reason", query_json)
        
        self.assertEqual(post_json["error"], query_json["error"])
        self.assertEqual(post_json["reason"], query_json["reason"])

    def test_query_method_allowed(self):
        # GET should return 405 with "POST,QUERY" in Allow header
        r = self.db.sess.request("GET", self.db.path("_find"))
        self.assertEqual(r.status_code, 405)
        allow = r.headers.get("Allow")
        self.assertIsNotNone(allow)
        methods = {method.strip() for method in allow.split(",")}
        self.assertEqual(methods, {"POST", "QUERY"})

    def test_bookmark_pagination_parity(self):
        selector = {"age": {"$gt": 20}}
        body_p1 = {
            "selector": selector,
            "limit": 2
        }
        headers = {"Content-Type": "application/json"}
        
        post_p1 = self.db.sess.request("POST", self.db.path("_find"), data=json.dumps(body_p1), headers=headers)
        query_p1 = self.db.sess.request("QUERY", self.db.path("_find"), data=json.dumps(body_p1), headers=headers)
        
        post_p1.raise_for_status()
        query_p1.raise_for_status()
        
        post_json = post_p1.json()
        query_json = query_p1.json()
        
        self.assertEqual(post_json.get("docs"), query_json.get("docs"))
        
        # Assert bookmark exists
        self.assertIn("bookmark", post_json)
        self.assertIn("bookmark", query_json)
        
        post_bookmark = post_json["bookmark"]
        query_bookmark = query_json["bookmark"]
        
        # Independent pagination chains
        body_p2_post = {
            "selector": selector,
            "limit": 2,
            "bookmark": post_bookmark
        }
        body_p2_query = {
            "selector": selector,
            "limit": 2,
            "bookmark": query_bookmark
        }
        
        post_p2 = self.db.sess.request("POST", self.db.path("_find"), data=json.dumps(body_p2_post), headers=headers)
        query_p2 = self.db.sess.request("QUERY", self.db.path("_find"), data=json.dumps(body_p2_query), headers=headers)
        
        post_p2.raise_for_status()
        query_p2.raise_for_status()
        
        self.assertEqual(post_p2.json().get("docs"), query_p2.json().get("docs"))
        
        # Cross-method bookmark compatibility
        body_p2_cross_post = {
            "selector": selector,
            "limit": 2,
            "bookmark": query_bookmark
        }
        body_p2_cross_query = {
            "selector": selector,
            "limit": 2,
            "bookmark": post_bookmark
        }
        
        post_p2_cross = self.db.sess.request("POST", self.db.path("_find"), data=json.dumps(body_p2_cross_post), headers=headers)
        query_p2_cross = self.db.sess.request("QUERY", self.db.path("_find"), data=json.dumps(body_p2_cross_query), headers=headers)
        
        post_p2_cross.raise_for_status()
        query_p2_cross.raise_for_status()
        
        self.assertEqual(post_p2_cross.json().get("docs"), query_p2_cross.json().get("docs"))


class NonPartitionedQueryMethodTests(mango.UserDocsTests, QueryMethodTestsMixin):
    pass


class PartitionedQueryMethodTests(mango.PartitionedUserDocsTests, QueryMethodTestsMixin):
    def test_partitioned_query_equivalence(self):
        # Since partitioned db has partition keys based on index, let's query partition "1"
        self.verify_post_query_equivalence({"selector": {"age": {"$gt": 20}}}, partition="1")
