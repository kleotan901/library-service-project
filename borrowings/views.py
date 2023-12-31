import datetime

from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from books.models import Book
from borrowings.models import Borrowing
from borrowings.serializers import (
    BorrowingSerializer,
    BorrowingDetailSerializer,
    BorrowingListSerializer,
)
from borrowings.tasks import send_message_new_borrowing
from telegram_notifications.models import Notification


class BorrowingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    GenericViewSet,
):
    serializer_class = BorrowingSerializer
    queryset = Borrowing.objects.all()
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return BorrowingDetailSerializer
        if self.action == "list":
            return BorrowingListSerializer
        return BorrowingSerializer

    def get_queryset(self):
        """Retrieve borrowings filtered by user_id and is_active"""
        queryset = self.queryset
        is_user = self.request.query_params.get("is_user")
        is_active = self.request.query_params.get("is_active")

        if is_user:
            queryset = Borrowing.objects.filter(user_id=is_user)

        if is_active:
            if is_active.lower() == "true":
                queryset = queryset.filter(actual_return_date__isnull=True)
            elif is_active.lower() == "false":
                queryset = queryset.filter(actual_return_date__isnull=False)

        if not self.request.user.is_staff:
            queryset = queryset.filter(user_id=self.request.user)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user_id=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        serializer.save()

        borrowed_book = serializer.data.get("book_id")
        book = Book.objects.get(id=borrowed_book)
        book.inventory -= 1
        book.save()

        message_text = f"Borrowing created - {book.title}({book.author})"
        chat_id = Notification.objects.get(user=request.user.id).chat_id
        send_message_new_borrowing.delay(chat_id, message_text)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(methods=["post"], detail=True, url_path="return")
    def return_book(self, request, pk):
        """Endpoint for return book"""
        borrowing = Borrowing.objects.get(id=pk)
        if borrowing.actual_return_date:
            return Response(
                {"message": "This book has already been returned"},
                status=status.HTTP_200_OK,
            )
        if borrowing.user_id.id == request.user.id:
            book = Book.objects.get(id=borrowing.book_id.id)
            book.inventory += 1
            book.save()
            borrowing.actual_return_date = datetime.datetime.now()
            borrowing.save()
            return Response({"message": "Book is returned"}, status=status.HTTP_200_OK)
        return Response(
            {"message": "User has no rights to return this book"},
            status=status.HTTP_403_FORBIDDEN,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="is_user",
                description="Filter borrowings by user id (ex. ?is_user=1)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="is_active",
                description="Filter borrowings by is_active (ex. ?is_active=true or ?is_active=false)",
                required=False,
                type=str,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(self, request, *args, **kwargs)
