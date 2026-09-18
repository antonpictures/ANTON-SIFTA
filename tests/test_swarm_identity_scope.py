from System.swarm_identity_scope import PrincipalScope, public_visitor_scope


def test_public_visitor_is_never_owner_even_when_alias_matches_owner_name():
    scope = public_visitor_scope("web-joey")
    assert scope.principal_id == "visitor:web-joey"
    assert scope.owner_authority is False
    assert scope.can_read(owner_only=True) is False
    assert scope.can_act() is False


def test_owner_authority_requires_both_authenticated_role_and_principal():
    assert PrincipalScope("owner-1", "s1", "owner", True).can_act() is True
    assert PrincipalScope("owner-1", "s1", "visitor", True).can_act() is False
    assert PrincipalScope("", "s1", "owner", True).can_act() is False


def test_scope_does_not_use_device_or_alias_as_authority():
    scope = PrincipalScope("visitor:s1", "s1", "visitor", False)
    assert not hasattr(scope, "device_authority")
    assert scope.can_read(owner_only=True) is False
