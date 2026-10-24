-- The typed column enforces the deployment dimension, while this trigger also
-- enforces the versioned profile dimension for direct/administrative inserts.
CREATE FUNCTION enforce_embedding_profile_dimensions() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected_dimensions integer;
BEGIN
 SELECT dimensions INTO expected_dimensions FROM embedding_profiles WHERE id=NEW.profile_id;
 IF expected_dimensions IS NULL OR vector_dims(NEW.embedding)<>expected_dimensions THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Embedding profile dimensions do not match vector';
 END IF;
 RETURN NEW;
END
$$;
CREATE TRIGGER tag_embedding_profile_dimensions
 BEFORE INSERT OR UPDATE ON tag_embeddings FOR EACH ROW
 EXECUTE FUNCTION enforce_embedding_profile_dimensions();
